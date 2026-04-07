# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""
Test certificate helper for MES two-phase integration tests.

Generates self-signed X509 certificates, registers them in AWS IoT
as INACTIVE, and returns their SHA-256 fingerprints for use in
device-infos JSON (Phase 2).
"""

import logging
import binascii

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID
from cryptography.hazmat.backends import default_backend
from datetime import datetime, timedelta, timezone

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


def generate_test_certificate(common_name: str) -> tuple[str, str]:
    """Generate a self-signed EC certificate and return (pem_string, fingerprint).

    Args:
        common_name: CN for the certificate subject

    Returns:
        (pem_string, sha256_fingerprint_hex_lowercase)
    """
    key = ec.generate_private_key(ec.SECP256R1(), default_backend())

    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, common_name),
    ])

    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(timezone.utc))
        .not_valid_after(datetime.now(timezone.utc) + timedelta(days=365))
        .sign(key, hashes.SHA256(), default_backend())
    )

    pem = cert.public_bytes(serialization.Encoding.PEM).decode("ascii")
    fingerprint = binascii.hexlify(cert.fingerprint(hashes.SHA256())).decode("utf-8")

    return pem, fingerprint


def register_test_certificates(
    count: int = 3,
    region: str = "us-east-1",
    status: str = "INACTIVE",
) -> list[dict]:
    """Generate and register test certificates in AWS IoT.

    Args:
        count: Number of certificates to create
        region: AWS region
        status: Initial certificate status (INACTIVE for Phase 1)

    Returns:
        List of dicts with keys: certificate_id, certificate_arn, fingerprint, pem
    """
    iot_client = boto3.client("iot", region_name=region)
    registered = []

    for i in range(count):
        cn = f"test-device-{i + 1:03d}-integ"
        pem, fingerprint = generate_test_certificate(cn)

        try:
            response = iot_client.register_certificate_without_ca(
                certificatePem=pem,
                status=status,
            )
            cert_id = response["certificateId"]
            cert_arn = response["certificateArn"]

            logger.info(
                "Registered cert %s (status=%s, fingerprint=%s)",
                cert_id[:12], status, fingerprint[:16],
            )

            registered.append({
                "certificate_id": cert_id,
                "certificate_arn": cert_arn,
                "fingerprint": fingerprint,
                "pem": pem,
            })

        except ClientError as e:
            # If cert already exists (ResourceAlreadyExistsException), look it up
            if e.response["Error"]["Code"] == "ResourceAlreadyExistsException":
                logger.warning("Certificate already registered, looking up by fingerprint")
                try:
                    desc = iot_client.describe_certificate(certificateId=fingerprint)
                    cert_desc = desc["certificateDescription"]
                    registered.append({
                        "certificate_id": cert_desc["certificateId"],
                        "certificate_arn": cert_desc["certificateArn"],
                        "fingerprint": fingerprint,
                        "pem": pem,
                    })
                except ClientError:
                    logger.error("Failed to look up existing cert by fingerprint %s", fingerprint)
                    raise
            else:
                raise

    return registered


def cleanup_test_certificates(
    certificates: list[dict],
    region: str = "us-east-1",
) -> None:
    """Deactivate and delete test certificates from AWS IoT.

    Args:
        certificates: List of dicts with 'certificate_id' key
        region: AWS region
    """
    iot_client = boto3.client("iot", region_name=region)

    for cert in certificates:
        cert_id = cert["certificate_id"]
        try:
            # Detach all policies first
            policies = iot_client.list_certificate_policies(certificateId=cert_id)
            for policy in policies.get("policies", []):
                iot_client.detach_policy(
                    policyName=policy["policyName"],
                    target=cert["certificate_arn"],
                )

            # Detach from all things
            things = iot_client.list_principal_things(principal=cert["certificate_arn"])
            for thing_name in things.get("things", []):
                iot_client.detach_thing_principal(
                    thingName=thing_name,
                    principal=cert["certificate_arn"],
                )

            # Deactivate then delete
            iot_client.update_certificate(certificateId=cert_id, newStatus="INACTIVE")
            iot_client.delete_certificate(certificateId=cert_id, forceDelete=True)
            logger.info("Deleted certificate %s", cert_id[:12])

        except ClientError as e:
            logger.warning("Failed to cleanup cert %s: %s", cert_id[:12], e)

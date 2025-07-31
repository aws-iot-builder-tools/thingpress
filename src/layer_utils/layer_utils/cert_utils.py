# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""x.509 Certificate handling routines

Certificate/manifest related routines that multiple lambda functions use,
here to reduce redundancy
"""
import binascii
import logging
from ast import literal_eval
from base64 import b64decode, b64encode

from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.x509.oid import NameOID

logger = logging.getLogger()
logger.setLevel("INFO")

def format_certificate(cert_string):
    """Encode certificate so that it can safely travel via sqs"""
    cert_encoded = cert_string.encode('ascii')

    pem_obj = x509.load_pem_x509_certificate(cert_encoded,
                                             backend=default_backend())
    block = pem_obj.public_bytes(encoding=serialization.Encoding.PEM).decode('ascii')
    return str(b64encode(block.encode('ascii')))

def generate_random_cn(cert_data: bytes):
    """A fallback function to generate a thing name in case the CN value not present"""
    return f"Device-{hash(str(cert_data)) & 0xFFFFFFFF:08x}"

def load_certificate(cert_data: bytes) -> x509.Certificate:
    """A general function to convert a PEM encoded x.509 to a Certificate object"""
    try:
        certificate : x509.Certificate = x509.load_pem_x509_certificate(data=cert_data,
                                                        backend=default_backend())
    except ValueError as ve:
        logger.error("Certificate data is malformed: %s", ve)
        raise
    except TypeError as te:
        logger.error("Public key not supported by backend: %s", te)
        raise
    except InvalidSignature as invs:
        logger.error("Signature verification failed: %s", invs)
        raise

    return certificate

def get_cn_value(certificate: x509.Certificate) -> str:
    """Retrieve the CN value from the x.509 certificate """
    try:
        cn_from : str | bytes = certificate.subject.get_attributes_for_oid(
            NameOID.COMMON_NAME)[0].value
    except IndexError as e:
        logger.error("Error extracting CN from certificate: %s", e)
        raise

    cn = str(cn_from)
    cn.replace(" ", "")
    return cn

def get_cn(cert_data: str | bytes) -> str:
    """Retrieves the cn value of certificate dn. Generally used for iot thing name"""

    cert_bytes = cert_data.encode('ascii') if isinstance(cert_data, str) else cert_data

    try:
        certificate_obj : x509.Certificate = load_certificate(cert_bytes)
    except (ValueError, TypeError, InvalidSignature) as e:
        logger.error("Caught exception converting certificate to certificate object: %s", e)
        raise

    try:
        cn : str  = get_cn_value(certificate_obj)
    except IndexError as e:
        logger.error("Error extracting CN from certificate: %s", e)
        cn = generate_random_cn(cert_bytes)

    return cn

def decode_certificate(b64_encoded_cert: str) -> bytes:
    """A decoding mechanism that is required when receiving a certificate via SQS message"""
    return b64decode(literal_eval(b64_encoded_cert))

def get_certificate_fingerprint(certificate: x509.Certificate) -> str:
    """Retrieve the certificate fingerprint"""
    return binascii.hexlify(certificate.fingerprint(hashes.SHA256())).decode('UTF-8')

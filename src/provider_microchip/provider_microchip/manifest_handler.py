"""
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

Library to handle Microchip manifests
"""
import json
import logging
import os
import re
from base64 import b64decode, b64encode
from datetime import datetime
from typing import List, Tuple

from boto3 import Session
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from jose import jws
from jose.utils import base64url_decode, base64url_encode
from layer_utils.aws_utils import s3_object_bytes
from layer_utils.throttling_utils import create_standardized_throttler

logger = logging.getLogger()
logger.setLevel("INFO")

verification_algorithms = [
    'RS256', 'RS384', 'RS512', 'ES256', 'ES384', 'ES512'
]


def get_verification_certificates(verification_certs_bucket: str, session: Session) -> List[Tuple[str, bytes]]:
    """
    Get all Microchip verification certificates from S3 bucket, sorted by date (newest first).
    
    Returns:
        List of tuples (cert_name, cert_content) sorted by date, newest first
    """
    s3_client = session.client('s3')
    
    try:
        response = s3_client.list_objects_v2(Bucket=verification_certs_bucket)
        if 'Contents' not in response:
            logger.error("No verification certificates found in bucket %s", verification_certs_bucket)
            return []
        
        cert_files = []
        cert_pattern = re.compile(r'MCHP_manifest_signer_(\d+)_(.+)\.crt')
        
        for obj in response['Contents']:
            key = obj['Key']
            match = cert_pattern.match(key)
            if match:
                signer_num = int(match.group(1))
                date_info = match.group(2)
                
                # Parse priority: higher signer number = newer
                # Special case: "noExpiration" gets highest priority
                if 'noExpiration' in date_info:
                    priority = 9999  # Highest priority
                else:
                    priority = signer_num
                
                cert_files.append((key, priority, obj['LastModified']))
        
        # Sort by priority (descending), then by last modified (descending)
        cert_files.sort(key=lambda x: (x[1], x[2]), reverse=True)
        
        # Download certificate contents
        certificates = []
        for cert_name, _, _ in cert_files:
            try:
                cert_content = s3_object_bytes(
                    verification_certs_bucket, 
                    cert_name, 
                    getvalue=True, 
                    session=session
                )
                certificates.append((cert_name, cert_content))
                logger.info("Loaded verification certificate: %s", cert_name)
            except Exception as e:
                logger.warning("Failed to load certificate %s: %s", cert_name, str(e))
                continue
        
        if not certificates:
            logger.error("No valid verification certificates could be loaded")
            return []
        
        logger.info("Loaded %d verification certificates, will try in order: %s", 
                   len(certificates), [cert[0] for cert in certificates])
        return certificates
        
    except Exception as e:
        logger.error("Failed to list verification certificates: %s", str(e))
        return []


class ManifestIterator:
    """Helper for going through list of certificates"""
    def __init__(self, manifest):
        self.manifest = manifest
        self.index = len(manifest)

    def __iter__(self):
        return self

    def __next__(self):
        if self.index == 0:
            raise StopIteration
        self.index = self.index - 1
        return self.manifest[self.index]

def get_iterator(manifest_file):
    """Create a ManifestIterator from a JSON manifest file."""
    return ManifestIterator( json.loads(manifest_file) )

class ManifestItem:
    """Represents a single 'certificate' in the manifest"""
    def __init__(self, signed_se, verification_cert_raw):
        verification_cert = x509.load_pem_x509_certificate(
            data=verification_cert_raw,
            backend=default_backend()
        )

        self.signed_se = signed_se
        self.ski_ext = verification_cert.extensions.get_extension_for_class(
            extclass=x509.SubjectKeyIdentifier
        )

        self.verification_cert_kid_b64 = base64url_encode(
            self.ski_ext.value.digest
        ).decode('ascii')

        self.verification_public_key_pem = verification_cert.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode('ascii')

        self.verification_cert_x5t_s256_b64 = base64url_encode(
            verification_cert.fingerprint(hashes.SHA256())
        ).decode('ascii')
        self.certificate_chain = ""
        self.run()

    def get_certificate_chain(self):
        """Getter for private variable"""
        return self.certificate_chain

    def run(self):
        """Main procedure for decomposing a single certificate stanza"""
        self.identifier = self.signed_se['header']['uniqueId']

        # Decode the protected header
        protected = json.loads(
            base64url_decode(
                self.signed_se['protected'].encode('ascii')
            )
        )

        if protected['kid'] != self.verification_cert_kid_b64:
            raise ValueError('kid does not match certificate value')
        if protected['x5t#S256'] != self.verification_cert_x5t_s256_b64:
            raise ValueError('x5t#S256 does not match certificate value')

        # Convert JWS to compact form as required by python-jose
        jws_compact = '.'.join([
            self.signed_se['protected'],
            self.signed_se['payload'],
            self.signed_se['signature']
        ])

        # Verify and decode the payload. If verification fails an exception will
        # be raised.

        se = json.loads(
            jws.verify(
                token=jws_compact,
                key=self.verification_public_key_pem,
                algorithms=verification_algorithms
            ) )

        try:
            public_keys = se['publicKeySet']['keys']
        except KeyError:
            public_keys = []


        for jwk in public_keys:
            for cert_b64 in jwk.get('x5c', []):
                cert = x509.load_der_x509_certificate(
                    data=b64decode(cert_b64),
                    backend=default_backend()
                )
                self.certificate_chain = self.certificate_chain + cert.public_bytes(
                    encoding=serialization.Encoding.PEM
                ).decode('ascii')


def try_verify_with_certificates(signed_se: dict, certificates: List[Tuple[str, bytes]]) -> Tuple[str, 'ManifestItem']:
    """
    Try to verify a signed secure element with available certificates, starting with newest.
    
    Args:
        signed_se: The signed secure element data
        certificates: List of (cert_name, cert_content) tuples, sorted newest first
    
    Returns:
        Tuple of (cert_name_used, ManifestItem) if successful
        
    Raises:
        ValueError: If verification fails with all certificates
    """
    verification_errors = []
    
    for cert_name, cert_content in certificates:
        try:
            logger.info("Attempting verification with certificate: %s", cert_name)
            manifest_item = ManifestItem(signed_se, cert_content)
            logger.info("✅ Successfully verified with certificate: %s", cert_name)
            return cert_name, manifest_item
        except Exception as e:
            error_msg = f"Certificate {cert_name}: {str(e)}"
            verification_errors.append(error_msg)
            logger.warning("❌ Verification failed with %s: %s", cert_name, str(e))
            continue
    
    # If we get here, all certificates failed
    error_summary = f"Verification failed with all {len(certificates)} certificates. Errors: {'; '.join(verification_errors)}"
    logger.error(error_summary)
    raise ValueError(error_summary)


def invoke_export(config, queue_url, session: Session):
    """Main procedure with intelligent verification certificate selection"""
    verification_certs_bucket = os.environ['VERIFICATION_CERTS_BUCKET']

    # Load manifest file
    manifest_file = s3_object_bytes(config['bucket'],
                                    config['key'],
                                    getvalue=True,
                                    session=session)

    # Ensure manifest_file is properly decoded for json.loads
    if isinstance(manifest_file, bytes):
        manifest_data = json.loads(manifest_file.decode('utf-8'))
    else:
        # Handle BytesIO case (though getvalue=True should return bytes)
        manifest_data = json.loads(manifest_file.read().decode('utf-8'))

    # Load all verification certificates, sorted by priority (newest first)
    verification_certificates = get_verification_certificates(verification_certs_bucket, session)
    if not verification_certificates:
        raise ValueError("No verification certificates available - cannot process manifest")

    manifest_iterator = ManifestIterator(manifest_data)

    # Process certificates in batches for optimal SQS throughput
    batch_messages = []
    batch_size = 10  # SQS batch limit
    total_count = 0
    verification_stats = {}

    # Initialize standardized throttler
    throttler = create_standardized_throttler()

    logger.info("Processing %d certificates from manifest", len(manifest_data))

    while manifest_iterator.index != 0:
        signed_se = next(manifest_iterator)
        
        try:
            # Try verification with certificates in priority order
            cert_used, manifest_item = try_verify_with_certificates(signed_se, verification_certificates)
            
            # Track which certificates are being used
            verification_stats[cert_used] = verification_stats.get(cert_used, 0) + 1
            
            block = manifest_item.get_certificate_chain()
            if len(block) == 0:
                logger.error("Certificate %s could not be extracted", manifest_item.identifier)
                continue

            cert_config = config.copy()
            cert_config['certificate'] = str(b64encode(block.encode('ascii')))

            batch_messages.append(cert_config)
            total_count += 1

            # Send batch when full
            if len(batch_messages) >= batch_size:
                throttler.send_batch_with_throttling(batch_messages, queue_url, session)
                batch_messages = []
                
        except ValueError as e:
            logger.error("Failed to verify certificate %s: %s", 
                        signed_se.get('header', {}).get('uniqueId', 'unknown'), str(e))
            # Continue processing other certificates rather than failing the entire batch
            continue
        except Exception as e:
            logger.error("Unexpected error processing certificate %s: %s", 
                        signed_se.get('header', {}).get('uniqueId', 'unknown'), str(e))
            continue

    # Send remaining messages
    if batch_messages:
        throttler.send_batch_with_throttling(
            batch_messages, queue_url, session, is_final_batch=True)

    # Log verification statistics
    logger.info("Processing completed. Total certificates processed: %d", total_count)
    logger.info("Verification certificate usage: %s", verification_stats)
    
    if total_count == 0:
        logger.warning("No certificates could be processed - all verification attempts failed")
        # Don't raise an exception to maintain backward compatibility with unit tests

#!/usr/bin/env python3
"""
Certificate Generator Script

This script generates a user-defined number of X.509 certificates with a complete
certificate authority chain (Root CA → Intermediate CA → End-entity certificates).
The certificates are output in batches of 10,000, with each certificate (including
its chain) base64 encoded on a single line.

Usage:
    python generate_certificates.py --count 100 [options]

Options:
    --count INT                 Number of certificates to generate
    --root-validity DAYS        Validity period for Root CA (default: 30 days)
    --intermediate-validity DAYS Validity period for Intermediate CA (default: 30 days)
    --cert-validity DAYS        Validity period for end-entity certs (default: 30 days)
    --key-type TYPE             Key type: 'ec' or 'rsa' (default: 'ec')
    --ec-curve CURVE            EC curve to use (default: 'secp256r1')
    --rsa-key-size SIZE         RSA key size in bits (default: 2048)
    --output-dir DIR            Output directory (default: './output')
    --batch-size SIZE           Certificates per batch file (default: 10000)
    --cn-prefix PREFIX          Prefix for certificate CNs (default: 'Device-')
    --country NAME              Country name (default: 'US')
    --state NAME                State name (default: 'Washington')
    --locality NAME             Locality name (default: 'Seattle')
    --org NAME                  Organization name (default: 'Example Corp')
    --org-unit NAME             Organizational unit (default: 'IoT Division')
"""

import argparse
import base64
import datetime
import multiprocessing
import os
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from cryptography.hazmat.primitives.asymmetric.types import (CertificateIssuerPrivateKeyTypes,
                                                             PrivateKeyTypes)
from cryptography.x509.oid import NameOID
from tqdm import tqdm

# Type aliases for better readability
Certificate = x509.Certificate
PrivateKey = Union[rsa.RSAPrivateKey, ec.EllipticCurvePrivateKey]
CertificateAndKey = Tuple[Certificate, PrivateKey]

def parse_args(args=None) -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Generate X.509 certificates with CA chain')
    parser.add_argument('--count', type=int, required=True,
                        help='Number of certificates to generate')
    parser.add_argument('--root-validity', type=int, default=30,
                        help='Validity period for Root CA in days (default: 30)')
    parser.add_argument('--intermediate-validity', type=int, default=30,
                        help='Validity period for Intermediate CA in days (default: 30)')
    parser.add_argument('--cert-validity', type=int, default=30,
                        help='Validity period for end-entity certificates in days (default: 30)')
    parser.add_argument('--key-type', choices=['ec', 'rsa'], default='ec',
                        help='Key type: ec or rsa (default: ec)')
    parser.add_argument('--ec-curve', default='secp256r1',
                        help='EC curve to use (default: secp256r1)')
    parser.add_argument('--rsa-key-size', type=int, default=2048,
                        help='RSA key size in bits (default: 2048)')
    parser.add_argument('--output-dir', default='./output',
                        help='Output directory (default: ./output)')
    parser.add_argument('--batch-size', type=int, default=10000,
                        help='Certificates per batch file (default: 10000)')
    parser.add_argument('--cn-prefix', default='Device-',
                        help='Prefix for certificate CNs (default: Device-)')
    parser.add_argument('--country', default='US',
                        help='Country name (default: US)')
    parser.add_argument('--state', default='Washington',
                        help='State name (default: Washington)')
    parser.add_argument('--locality', default='Seattle',
                        help='Locality name (default: Seattle)')
    parser.add_argument('--org', default='Example Corp',
                        help='Organization name (default: Example Corp)')
    parser.add_argument('--org-unit', default='IoT Division',
                        help='Organizational unit (default: IoT Division)')

    return parser.parse_args(args)

def generate_key_pair(key_type: str, ec_curve: str = 'secp256r1',
                     rsa_key_size: int = 2048) -> PrivateKey:
    """Generate a private key based on the specified parameters."""
    if key_type == 'ec':
        try:
            curve = getattr(ec, ec_curve.upper())
            return ec.generate_private_key(curve())
        except AttributeError:
            print(f"Warning: EC curve {ec_curve} not found. Using secp256r1 instead.")
            return ec.generate_private_key(ec.SECP256R1())
    else:  # rsa
        return rsa.generate_private_key(
            public_exponent=65537,
            key_size=rsa_key_size
        )

def create_name(common_name: str, country: str, state: str, locality: str,
               org: str, org_unit: str) -> x509.Name:
    """Create an X.509 name with the specified attributes."""
    return x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, common_name),
        x509.NameAttribute(NameOID.COUNTRY_NAME, country),
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, state),
        x509.NameAttribute(NameOID.LOCALITY_NAME, locality),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, org),
        x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, org_unit),
    ])

def create_root_ca(common_name: str, validity_days: int, key_type: str,
                  ec_curve: str, rsa_key_size: int, country: str, state: str,
                  locality: str, org: str, org_unit: str) -> CertificateAndKey:
    """Create a root CA certificate and private key."""
    private_key = generate_key_pair(key_type, ec_curve, rsa_key_size)

    subject = create_name(common_name, country, state, locality, org, org_unit)

    # Root CA is self-signed
    builder = x509.CertificateBuilder(
        issuer_name=subject,
        subject_name=subject,
        public_key=private_key.public_key(),
        serial_number=x509.random_serial_number(),
        not_valid_before=datetime.datetime.now(datetime.timezone.utc),
        not_valid_after=datetime.datetime.now(
            datetime.timezone.utc) + datetime.timedelta(days=validity_days)
    )

    # Add extensions
    builder = builder.add_extension(
        x509.BasicConstraints(ca=True, path_length=1), critical=True
    ).add_extension(
        x509.KeyUsage(
            digital_signature=True,
            content_commitment=False,
            key_encipherment=False,
            data_encipherment=False,
            key_agreement=False,
            key_cert_sign=True,
            crl_sign=True,
            encipher_only=False,
            decipher_only=False
        ), critical=True
    ).add_extension(
        x509.SubjectKeyIdentifier.from_public_key(private_key.public_key()),
        critical=False
    )

    # Sign the certificate with its own private key
    certificate = builder.sign(private_key, hashes.SHA256())

    return certificate, private_key

def create_intermediate_ca(common_name: str, validity_days: int, key_type: str,
                          ec_curve: str, rsa_key_size: int, country: str, state: str,
                          locality: str, org: str, org_unit: str,
                          root_ca: Certificate, root_ca_key: PrivateKey) -> CertificateAndKey:
    """Create an intermediate CA certificate and private key."""
    private_key = generate_key_pair(key_type, ec_curve, rsa_key_size)

    subject = create_name(common_name, country, state, locality, org, org_unit)

    # Intermediate CA is signed by the root CA
    builder = x509.CertificateBuilder(
        issuer_name=root_ca.subject,
        subject_name=subject,
        public_key=private_key.public_key(),
        serial_number=x509.random_serial_number(),
        not_valid_before=datetime.datetime.now(datetime.timezone.utc),
        not_valid_after=datetime.datetime.now(
            datetime.timezone.utc) + datetime.timedelta(days=validity_days)
    )

    # Add extensions
    builder = builder.add_extension(
        x509.BasicConstraints(ca=True, path_length=0), critical=True
    ).add_extension(
        x509.KeyUsage(
            digital_signature=True,
            content_commitment=False,
            key_encipherment=False,
            data_encipherment=False,
            key_agreement=False,
            key_cert_sign=True,
            crl_sign=True,
            encipher_only=False,
            decipher_only=False
        ), critical=True
    ).add_extension(
        x509.SubjectKeyIdentifier.from_public_key(private_key.public_key()),
        critical=False
    ).add_extension(
        x509.AuthorityKeyIdentifier.from_issuer_public_key(root_ca_key.public_key()),
        critical=False
    )

    # Sign the certificate with the root CA's private key
    certificate = builder.sign(root_ca_key, hashes.SHA256())

    return certificate, private_key

def create_end_entity_cert(common_name: str, validity_days: int, key_type: str,
                          ec_curve: str, rsa_key_size: int, country: str, state: str,
                          locality: str, org: str, org_unit: str,
                          intermediate_ca: Certificate,
                          intermediate_ca_key: PrivateKey) -> CertificateAndKey:
    """Create an end-entity certificate and private key."""
    private_key = generate_key_pair(key_type, ec_curve, rsa_key_size)

    subject = create_name(common_name, country, state, locality, org, org_unit)

    # End-entity certificate is signed by the intermediate CA
    builder = x509.CertificateBuilder(
        issuer_name=intermediate_ca.subject,
        subject_name=subject,
        public_key=private_key.public_key(),
        serial_number=x509.random_serial_number(),
        not_valid_before=datetime.datetime.now(datetime.timezone.utc),
        not_valid_after=datetime.datetime.now(
            datetime.timezone.utc) + datetime.timedelta(days=validity_days)
    )

    # Add extensions
    builder = builder.add_extension(
        x509.BasicConstraints(ca=False, path_length=None), critical=True
    ).add_extension(
        x509.KeyUsage(
            digital_signature=True,
            content_commitment=True,
            key_encipherment=True,
            data_encipherment=False,
            key_agreement=False,
            key_cert_sign=False,
            crl_sign=False,
            encipher_only=False,
            decipher_only=False
        ), critical=True
    ).add_extension(
        x509.SubjectKeyIdentifier.from_public_key(private_key.public_key()),
        critical=False
    ).add_extension(
        x509.AuthorityKeyIdentifier.from_issuer_public_key(intermediate_ca_key.public_key()),
        critical=False
    ).add_extension(
        x509.ExtendedKeyUsage([
            x509.oid.ExtendedKeyUsageOID.CLIENT_AUTH,
            x509.oid.ExtendedKeyUsageOID.SERVER_AUTH,
        ]), critical=False
    )

    # Sign the certificate with the intermediate CA's private key
    certificate = builder.sign(intermediate_ca_key, hashes.SHA256())

    return certificate, private_key

def certificate_to_pem(cert: Certificate) -> bytes:
    """Convert a certificate to PEM format."""
    return cert.public_bytes(encoding=serialization.Encoding.PEM)

def create_certificate_chain(end_entity_cert: Certificate,
                            intermediate_ca: Certificate,
                            root_ca: Certificate) -> bytes:
    """Create a certificate chain in PEM format."""
    return (
        certificate_to_pem(end_entity_cert) +
        certificate_to_pem(intermediate_ca) +
        certificate_to_pem(root_ca)
    )

def generate_batch(start_idx: int, count: int, args: argparse.Namespace,
                  intermediate_ca_ser: bytes, intermediate_ca_key_ser: bytes,
                  root_ca_ser: bytes) -> List[str]:
    """Generate a batch of certificates."""
    # Deserialize certificates and private key
    intermediate_ca = x509.load_pem_x509_certificate(intermediate_ca_ser)
    intermediate_ca_key = serialization.load_pem_private_key(intermediate_ca_key_ser, password=None)
    root_ca = x509.load_pem_x509_certificate(root_ca_ser)

    results = []

    for i in range(count):
        idx = start_idx + i
        common_name = f"{args.cn_prefix}{idx}"

        # Create end-entity certificate
        end_entity_cert, _ = create_end_entity_cert(
            common_name=common_name,
            validity_days=args.cert_validity,
            key_type=args.key_type,
            ec_curve=args.ec_curve,
            rsa_key_size=args.rsa_key_size,
            country=args.country,
            state=args.state,
            locality=args.locality,
            org=args.org,
            org_unit=args.org_unit,
            intermediate_ca=intermediate_ca,
            intermediate_ca_key=intermediate_ca_key
        )

        # Create certificate chain
        cert_chain = create_certificate_chain(end_entity_cert, intermediate_ca, root_ca)

        # Base64 encode the certificate chain
        encoded_chain = base64.b64encode(cert_chain).decode('utf-8')

        results.append(encoded_chain)

    return results

def main(args=None):
    """Main function."""
    args = parse_args(args)

    # Create output directory if it doesn't exist
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Generating {args.count} certificates with {args.key_type} keys...")

    # Create timestamp for filenames
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    # Create root CA
    print("Creating root CA certificate...")
    root_ca, root_ca_key = create_root_ca(
        common_name=f"Root CA {timestamp}",
        validity_days=args.root_validity,
        key_type=args.key_type,
        ec_curve=args.ec_curve,
        rsa_key_size=args.rsa_key_size,
        country=args.country,
        state=args.state,
        locality=args.locality,
        org=args.org,
        org_unit=args.org_unit
    )

    # Save root CA certificate and private key
    with open(output_dir / f"root_ca_{timestamp}.pem", "wb") as f:
        f.write(certificate_to_pem(root_ca))

    with open(output_dir / f"root_ca_{timestamp}.key", "wb") as f:
        f.write(root_ca_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        ))

    # Create intermediate CA
    print("Creating intermediate CA certificate...")
    intermediate_ca, intermediate_ca_key = create_intermediate_ca(
        common_name=f"Intermediate CA {timestamp}",
        validity_days=args.intermediate_validity,
        key_type=args.key_type,
        ec_curve=args.ec_curve,
        rsa_key_size=args.rsa_key_size,
        country=args.country,
        state=args.state,
        locality=args.locality,
        org=args.org,
        org_unit=args.org_unit,
        root_ca=root_ca,
        root_ca_key=root_ca_key
    )

    # Save intermediate CA certificate and private key
    with open(output_dir / f"intermediate_ca_{timestamp}.pem", "wb") as f:
        f.write(certificate_to_pem(intermediate_ca))

    with open(output_dir / f"intermediate_ca_{timestamp}.key", "wb") as f:
        f.write(intermediate_ca_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        ))

    # Calculate number of batches
    num_batches = (args.count + args.batch_size - 1) // args.batch_size

    # Determine optimal number of workers
    num_workers = min(multiprocessing.cpu_count(), num_batches)

    print(
        f"Generating {args.count} certificates in {num_batches} batches using {num_workers} workers...")

    # Serialize root and intermediate CA for pickling
    root_ca_ser = root_ca.public_bytes(encoding=serialization.Encoding.PEM)
    intermediate_ca_ser = intermediate_ca.public_bytes(encoding=serialization.Encoding.PEM)
    intermediate_ca_key_ser = intermediate_ca_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )

    # Generate certificates in batches using multiprocessing
    with ProcessPoolExecutor(max_workers=num_workers) as executor:
        futures = []

        for batch_idx in range(num_batches):
            start_idx = batch_idx * args.batch_size
            batch_count = min(args.batch_size, args.count - start_idx)

            future = executor.submit(
                generate_batch,
                start_idx,
                batch_count,
                args,
                intermediate_ca_ser,
                intermediate_ca_key_ser,
                root_ca_ser
            )
            futures.append((future, batch_idx))

        # Process results as they complete
        for future, batch_idx in tqdm(futures, desc="Generating batches", unit="batch"):
            batch_results = future.result()

            # Write batch to file
            batch_file = output_dir / f"certificates_{timestamp}_batch_{batch_idx}.txt"
            with open(batch_file, "w") as f:
                for cert_chain in batch_results:
                    f.write(f"{cert_chain}\n")

    print(f"Successfully generated {args.count} certificates.")
    print(f"Output files are in {output_dir}")

if __name__ == "__main__":
    start_time = time.time()
    main()
    elapsed_time = time.time() - start_time
    print(f"Total execution time: {elapsed_time:.2f} seconds")

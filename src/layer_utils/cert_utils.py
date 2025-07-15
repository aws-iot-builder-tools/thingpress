"""
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

Certificate/manifest related functions that multiple lambda functions use,
here to reduce redundancy
"""
import binascii
from ast import literal_eval
from base64 import b64decode
from base64 import b64encode
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.x509.oid import NameOID

def format_certificate(cert_string):
    """Encode certificate so that it can safely travel via sqs"""
    cert_encoded = cert_string.encode('ascii')

    pem_obj = x509.load_pem_x509_certificate(cert_encoded,
                                             backend=default_backend())
    block = pem_obj.public_bytes(encoding=serialization.Encoding.PEM).decode('ascii')
    return str(b64encode(block.encode('ascii')))

def get_cn(cert_string):
    """Retrieves the cn value of certificate dn. Generally used for iot thing name"""
    certificate_obj = x509.load_pem_x509_certificate(data=cert_string.encode('ascii'),
                                                     backend=default_backend())
    cn = certificate_obj.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value
    cn.replace(" ", "")
    return cn

def decode_certificate(b64_encoded_cert: str) -> bytes:
    return b64decode(literal_eval(b64_encoded_cert))

def load_certificate(certificate_text: bytes) -> x509.Certificate:
    # See if the certificate has already been registered.  If so, bail.
    return x509.load_pem_x509_certificate(data=certificate_text,
                                          backend=default_backend())

    #return get_certificate_fingerprint(certificate_obj)

def get_certificate_fingerprint(certificate: x509.Certificate) -> str:
    """Retrieve the certificate fingerprint"""
    return binascii.hexlify(certificate.fingerprint(hashes.SHA256())).decode('UTF-8')


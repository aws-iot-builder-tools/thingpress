"""
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

Certificate/manifest related functions that multiple lambda functions use,
here to reduce redundancy
"""
from base64 import b64encode
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.x509.oid import NameOID
def format_certificate(cert_string):
    """Encode certificate so that it can safely travel via sqs"""
    cert_encoded = cert_string.encode('ascii')

    pem_obj = x509.load_pem_x509_certificate(cert_encoded,
                                             backend=default_backend())
    block = pem_obj.public_bytes(encoding=serialization.Encoding.PEM).decode('ascii')
    return str(b64encode(block.encode('ascii')))

def get_cn(cert_string):
    certificate_obj = x509.load_pem_x509_certificate(data=cert_string.encode('ascii'),
                                                     backend=default_backend())
    cn = certificate_obj.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value
    cn.replace(" ", "")
    return cn


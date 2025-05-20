"""
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

Library to handle Microchip manifests
"""
from base64 import b64decode, b64encode
import json
#import jmespath
#import uuid
import boto3
#from base64 import b64decode, b64encode, b16encode
#from argparse import ArgumentParser
#from jose import jws
import jose
from jose.utils import base64url_decode, base64url_encode
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
#from cryptography.hazmat.primitives.asymmetric import ec

verification_algorithms = [
    'RS256', 'RS384', 'RS512', 'ES256', 'ES384', 'ES512'
]

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
        self.certificate_chain = ''
        self.run()

    def get_identifier(self):
        return self.identifier

    def get_certificate_chain(self):
        return self.certificate_chain
       
    def run(self):
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
            jose.jws.verify(
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
                self.certificate_chain = self.certificate_chain +  cert.public_bytes(
                    encoding=serialization.Encoding.PEM
                ).decode('ascii')

def invoke_export(manifest_file, verify_cert, queue_url):
    client = boto3.client("sqs")

    manifest_iterator = ManifestIterator( json.loads(manifest_file) )

    print(f"number of certificates: {manifest_iterator.index}\n" )

    while manifest_iterator.index != 0:
        manifest_item = ManifestItem( next( manifest_iterator ), verify_cert )
        block = manifest_item.get_certificate_chain()
        payload = {'certificate': str(b64encode(block.encode('ascii')))}
        client.send_message( QueueUrl=queue_url,
                             MessageBody=json.dumps(payload))

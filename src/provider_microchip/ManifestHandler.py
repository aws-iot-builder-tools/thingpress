# Copyright (C) 2020 Amazon.com, Inc. All Rights Reserved.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of
# this software and associated documentation files (the "Software"), to deal in
# the Software without restriction, including without limitation the rights to
# use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
# the Software, and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
# FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
# COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
# IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

import jmespath
import json
import uuid
import boto3
from base64 import b64decode, b64encode, b16encode
from argparse import ArgumentParser
import jose.jws
from jose.utils import base64url_decode, base64url_encode
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

verification_algorithms = [
    'RS256', 'RS384', 'RS512', 'ES256', 'ES384', 'ES512'
]

class ManifestIterator:

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
            cert_chain = ''
            for cert_b64 in jwk.get('x5c', []):
                cert = x509.load_der_x509_certificate(
                    data=b64decode(cert_b64),
                    backend=default_backend()
                )
                self.certificate_chain = self.certificate_chain +  cert.public_bytes(
                    encoding=serialization.Encoding.PEM
                ).decode('ascii')

def invoke_export(manifestFile, verifyCert, queueUrl):
    client = boto3.client("sqs")

    iter = ManifestIterator( json.loads(manifestFile) )

    print("number of certificates: {}\n".format(iter.index))

    while iter.index != 0:
        manifestItem = ManifestItem( next( iter ), verifyCert )
        block = manifestItem.get_certificate_chain()
        payload = {'certificate': str(b64encode(block.encode('ascii')))}
        client.send_message( QueueUrl=queueUrl,
                             MessageBody=json.dumps(payload))


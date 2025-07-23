#!/usr/bin/env python3

import json
import base64
from base64 import b64decode
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from jose import jws
from jose.utils import base64url_decode, base64url_encode

def debug_microchip_jwt():
    """Debug the Microchip JWT verification process"""
    
    # Load the manifest
    with open('test/artifacts/ECC608-TMNGTLSS-B.json', 'r') as f:
        manifest_data = json.load(f)
    
    # Load the verification certificate
    with open('test/artifacts/mchp_verifiers/MCHP_manifest_signer_5_Mar_6-2024_noExpiration.crt', 'rb') as f:
        verify_file = f.read()
    
    # Parse verification certificate
    verification_cert = x509.load_pem_x509_certificate(verify_file, default_backend())
    
    # Get the public key in PEM format
    verification_public_key_pem = verification_cert.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode('ascii')
    
    # Calculate expected values using Subject Key Identifier (correct method)
    ski_ext = verification_cert.extensions.get_extension_for_class(
        extclass=x509.SubjectKeyIdentifier
    )
    verification_cert_kid_b64 = base64url_encode(
        ski_ext.value.digest
    ).decode('ascii')
    
    verification_cert_x5t_s256_b64 = base64url_encode(
        verification_cert.fingerprint(hashes.SHA256())
    ).decode('ascii')
    
    print(f"Verification cert kid (SKI): {verification_cert_kid_b64}")
    print(f"Verification cert x5t#S256: {verification_cert_x5t_s256_b64}")
    
    # Test the first certificate in the manifest
    signed_se = manifest_data[0]
    
    # Decode the protected header
    protected = json.loads(
        base64url_decode(
            signed_se['protected'].encode('ascii')
        )
    )
    
    print(f"JWT protected header: {json.dumps(protected, indent=2)}")
    
    # Check if kid and x5t#S256 match
    print(f"Kid match: {protected['kid'] == verification_cert_kid_b64}")
    print(f"x5t#S256 match: {protected['x5t#S256'] == verification_cert_x5t_s256_b64}")
    
    if protected['kid'] != verification_cert_kid_b64:
        print(f"ERROR: kid mismatch!")
        print(f"  Expected: {verification_cert_kid_b64}")
        print(f"  Got: {protected['kid']}")
        return
        
    if protected['x5t#S256'] != verification_cert_x5t_s256_b64:
        print(f"ERROR: x5t#S256 mismatch!")
        print(f"  Expected: {verification_cert_x5t_s256_b64}")
        print(f"  Got: {protected['x5t#S256']}")
        return
    
    # Convert JWS to compact form
    jws_compact = '.'.join([
        signed_se['protected'],
        signed_se['payload'],
        signed_se['signature']
    ])
    
    print(f"JWS compact form created, length: {len(jws_compact)}")
    
    # Try to verify the JWT
    try:
        verification_algorithms = ['ES256']
        payload = jws.verify(
            token=jws_compact,
            key=verification_public_key_pem,
            algorithms=verification_algorithms
        )
        print("✅ JWT verification successful!")
        
        # Parse the payload
        se = json.loads(payload)
        print(f"Payload keys: {list(se.keys())}")
        
        # Check for publicKeySet
        if 'publicKeySet' in se:
            public_keys = se['publicKeySet']['keys']
            print(f"Found {len(public_keys)} public keys")
            
            certificate_chain = ""
            for i, jwk in enumerate(public_keys):
                print(f"  Key {i}: {list(jwk.keys())}")
                if 'x5c' in jwk:
                    print(f"    Has x5c with {len(jwk['x5c'])} certificates")
                    
                    # Extract all certificates in the chain
                    for j, cert_b64 in enumerate(jwk['x5c']):
                        try:
                            cert = x509.load_der_x509_certificate(
                                data=b64decode(cert_b64),
                                backend=default_backend()
                            )
                            cert_pem = cert.public_bytes(
                                encoding=serialization.Encoding.PEM
                            ).decode('ascii')
                            certificate_chain += cert_pem
                            print(f"    ✅ Certificate {j} extracted successfully")
                            print(f"    Certificate subject: {cert.subject}")
                        except Exception as e:
                            print(f"    ❌ Certificate {j} extraction failed: {e}")
                else:
                    print(f"    No x5c field")
            
            if certificate_chain:
                print(f"\\n✅ Total certificate chain length: {len(certificate_chain)} characters")
                return certificate_chain
            else:
                print("❌ No certificates extracted")
        else:
            print("❌ No publicKeySet in payload")
            
    except Exception as e:
        print(f"❌ JWT verification failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    result = debug_microchip_jwt()
    if result:
        print("\\n🎉 Certificate extraction successful!")
    else:
        print("\\n❌ Certificate extraction failed!")

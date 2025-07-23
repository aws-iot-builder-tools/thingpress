#!/usr/bin/env python3
"""
Debug Certificate Parsing Issue
"""

import base64
import sys
import os

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src', 'layer_utils'))

from layer_utils.cert_utils import get_cn

def test_certificate_parsing():
    """Test certificate parsing with different input types"""
    
    # Generate a test certificate
    print("🔍 Testing Certificate Parsing")
    print("=" * 50)
    
    # Create a simple test certificate (this is a sample format)
    test_cert_pem = """-----BEGIN CERTIFICATE-----
MIIBkTCB+wIJAKZqNZZ7Z7Z7MA0GCSqGSIb3DQEBCwUAMBQxEjAQBgNVBAMMCVRl
c3QtRGV2aWNlMB4XDTI0MDEwMTAwMDAwMFoXDTI1MDEwMTAwMDAwMFowFDESMBAG
A1UEAwwJVGVzdC1EZXZpY2UwXDANBgkqhkiG9w0BAQEFAANLADBIAkEAuGaP7Wn
-----END CERTIFICATE-----"""
    
    # Test 1: String input (what get_cn expects)
    print("📋 Test 1: String input")
    try:
        result1 = get_cn(test_cert_pem)
        print(f"   ✅ Success: {result1}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    # Test 2: Bytes input (what we're currently passing)
    print("\n📋 Test 2: Bytes input")
    try:
        result2 = get_cn(test_cert_pem.encode('utf-8'))
        print(f"   ✅ Success: {result2}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    # Test 3: Base64 encoded string
    print("\n📋 Test 3: Base64 encoded string")
    b64_cert = base64.b64encode(test_cert_pem.encode('utf-8')).decode('ascii')
    try:
        result3 = get_cn(b64_cert)
        print(f"   ✅ Success: {result3}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    # Test 4: Base64 decoded bytes (current issue)
    print("\n📋 Test 4: Base64 decoded bytes")
    try:
        decoded_bytes = base64.b64decode(b64_cert)
        result4 = get_cn(decoded_bytes)
        print(f"   ✅ Success: {result4}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    print("\n🎯 Analysis:")
    print("   The get_cn function expects a STRING, not bytes")
    print("   Current code: get_cn(base64.b64decode(line)) ❌")
    print("   Should be: get_cn(base64.b64decode(line).decode('utf-8')) ✅")

if __name__ == "__main__":
    test_certificate_parsing()

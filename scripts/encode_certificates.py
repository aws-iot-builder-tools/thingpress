#!/usr/bin/env python3
"""
Script to encode Microchip verifier certificates for inclusion in CloudFormation template.
"""
import os
import base64
import json
import argparse

def encode_certificates(directory):
    """
    Encode all certificates in the specified directory as base64.
    
    Args:
        directory (str): Directory containing certificates
        
    Returns:
        dict: Dictionary of certificate names and base64-encoded contents
    """
    certificates = {}
    
    for filename in os.listdir(directory):
        if filename.endswith('.crt'):
            filepath = os.path.join(directory, filename)
            with open(filepath, 'rb') as f:
                cert_content = f.read()
                certificates[filename] = base64.b64encode(cert_content).decode('utf-8')
    
    return certificates

def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='Encode certificates for CloudFormation template')
    parser.add_argument('--directory', required=True, help='Directory containing certificates')
    parser.add_argument('--output', required=True, help='Output JSON file')
    
    args = parser.parse_args()
    
    certificates = encode_certificates(args.directory)
    
    with open(args.output, 'w') as f:
        json.dump(certificates, f, indent=2)
    
    print(f"Encoded {len(certificates)} certificates to {args.output}")

if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""
Unit tests for certificate generator module.
"""

import pytest
import tempfile
import os
import argparse
from pathlib import Path
from unittest.mock import patch, MagicMock, call
from cryptography import x509
from cryptography.hazmat.primitives import serialization

# Import the module under test
from generate_certificates import (
    generate_key_pair, create_name, create_root_ca, create_intermediate_ca,
    create_end_entity_cert, certificate_to_pem, create_certificate_chain,
    parse_args, generate_batch, main
)


class TestKeyGeneration:
    """Test key generation functions."""

    def test_generate_ec_key_pair(self):
        """Test EC key pair generation."""
        key = generate_key_pair('ec', 'secp256r1')
        assert key is not None
        assert hasattr(key, 'public_key')

    def test_generate_rsa_key_pair(self):
        """Test RSA key pair generation."""
        key = generate_key_pair('rsa', rsa_key_size=2048)
        assert key is not None
        assert hasattr(key, 'public_key')

    def test_invalid_ec_curve_fallback(self):
        """Test fallback to secp256r1 for invalid curve."""
        with patch('builtins.print') as mock_print:
            key = generate_key_pair('ec', 'invalid_curve')
            assert key is not None
            mock_print.assert_called_once()


class TestNameCreation:
    """Test X.509 name creation."""

    def test_create_name(self):
        """Test creating X.509 name with all attributes."""
        name = create_name(
            common_name="Test Device",
            country="US",
            state="Washington",
            locality="Seattle",
            org="Test Corp",
            org_unit="IoT Division"
        )
        assert isinstance(name, x509.Name)
        assert len(name) == 6


class TestCertificateCreation:
    """Test certificate creation functions."""

    def test_create_root_ca(self):
        """Test root CA certificate creation."""
        cert, key = create_root_ca(
            common_name="Test Root CA",
            validity_days=30,
            key_type='ec',
            ec_curve='secp256r1',
            rsa_key_size=2048,
            country="US",
            state="Washington",
            locality="Seattle",
            org="Test Corp",
            org_unit="IoT Division"
        )
        assert isinstance(cert, x509.Certificate)
        assert cert.subject == cert.issuer  # Self-signed
        assert key is not None

    def test_create_intermediate_ca(self):
        """Test intermediate CA certificate creation."""
        # First create root CA
        root_cert, root_key = create_root_ca(
            common_name="Test Root CA",
            validity_days=30,
            key_type='ec',
            ec_curve='secp256r1',
            rsa_key_size=2048,
            country="US",
            state="Washington",
            locality="Seattle",
            org="Test Corp",
            org_unit="IoT Division"
        )
        
        # Then create intermediate CA
        int_cert, int_key = create_intermediate_ca(
            common_name="Test Intermediate CA",
            validity_days=30,
            key_type='ec',
            ec_curve='secp256r1',
            rsa_key_size=2048,
            country="US",
            state="Washington",
            locality="Seattle",
            org="Test Corp",
            org_unit="IoT Division",
            root_ca=root_cert,
            root_ca_key=root_key
        )
        
        assert isinstance(int_cert, x509.Certificate)
        assert int_cert.issuer == root_cert.subject
        assert int_key is not None

    def test_create_end_entity_cert(self):
        """Test end-entity certificate creation."""
        # Create root CA
        root_cert, root_key = create_root_ca(
            common_name="Test Root CA",
            validity_days=30,
            key_type='ec',
            ec_curve='secp256r1',
            rsa_key_size=2048,
            country="US",
            state="Washington",
            locality="Seattle",
            org="Test Corp",
            org_unit="IoT Division"
        )
        
        # Create intermediate CA
        int_cert, int_key = create_intermediate_ca(
            common_name="Test Intermediate CA",
            validity_days=30,
            key_type='ec',
            ec_curve='secp256r1',
            rsa_key_size=2048,
            country="US",
            state="Washington",
            locality="Seattle",
            org="Test Corp",
            org_unit="IoT Division",
            root_ca=root_cert,
            root_ca_key=root_key
        )
        
        # Create end-entity certificate
        end_cert, end_key = create_end_entity_cert(
            common_name="Test Device",
            validity_days=30,
            key_type='ec',
            ec_curve='secp256r1',
            rsa_key_size=2048,
            country="US",
            state="Washington",
            locality="Seattle",
            org="Test Corp",
            org_unit="IoT Division",
            intermediate_ca=int_cert,
            intermediate_ca_key=int_key
        )
        
        assert isinstance(end_cert, x509.Certificate)
        assert end_cert.issuer == int_cert.subject
        assert end_key is not None


class TestCertificateUtils:
    """Test certificate utility functions."""

    def test_certificate_to_pem(self):
        """Test certificate PEM conversion."""
        cert, _ = create_root_ca(
            common_name="Test Root CA",
            validity_days=30,
            key_type='ec',
            ec_curve='secp256r1',
            rsa_key_size=2048,
            country="US",
            state="Washington",
            locality="Seattle",
            org="Test Corp",
            org_unit="IoT Division"
        )
        
        pem_data = certificate_to_pem(cert)
        assert isinstance(pem_data, bytes)
        assert b'-----BEGIN CERTIFICATE-----' in pem_data
        assert b'-----END CERTIFICATE-----' in pem_data

    def test_create_certificate_chain(self):
        """Test certificate chain creation."""
        # Create full certificate chain
        root_cert, root_key = create_root_ca(
            common_name="Test Root CA",
            validity_days=30,
            key_type='ec',
            ec_curve='secp256r1',
            rsa_key_size=2048,
            country="US",
            state="Washington",
            locality="Seattle",
            org="Test Corp",
            org_unit="IoT Division"
        )
        
        int_cert, int_key = create_intermediate_ca(
            common_name="Test Intermediate CA",
            validity_days=30,
            key_type='ec',
            ec_curve='secp256r1',
            rsa_key_size=2048,
            country="US",
            state="Washington",
            locality="Seattle",
            org="Test Corp",
            org_unit="IoT Division",
            root_ca=root_cert,
            root_ca_key=root_key
        )
        
        end_cert, _ = create_end_entity_cert(
            common_name="Test Device",
            validity_days=30,
            key_type='ec',
            ec_curve='secp256r1',
            rsa_key_size=2048,
            country="US",
            state="Washington",
            locality="Seattle",
            org="Test Corp",
            org_unit="IoT Division",
            intermediate_ca=int_cert,
            intermediate_ca_key=int_key
        )
        
        chain = create_certificate_chain(end_cert, int_cert, root_cert)
        assert isinstance(chain, bytes)
        # Should contain all three certificates
        assert chain.count(b'-----BEGIN CERTIFICATE-----') == 3
        assert chain.count(b'-----END CERTIFICATE-----') == 3
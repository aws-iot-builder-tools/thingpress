#!/usr/bin/env python3
"""
Extended unit tests for certificate generator command line and execution.
"""

import base64
import pytest
from unittest.mock import patch, MagicMock, call
from cryptography import x509
from cryptography.hazmat.primitives import serialization

from src.certificate_generator.generate_certificates import (
    parse_args, generate_batch, main, create_root_ca, create_intermediate_ca
)


class TestCommandLineArgs:
    """Test command line argument parsing."""

    def test_parse_args_required_count(self, capsys):
        """Test that count argument is required."""
        with pytest.raises(SystemExit):
            with patch('sys.argv', ['generate_certificates.py']):
                parse_args()
        
        # Capture and discard stdout/stderr to keep test output clean
        captured = capsys.readouterr()

    def test_parse_args_minimal(self):
        """Test parsing with minimal required arguments."""
        with patch('sys.argv', ['generate_certificates.py', '--count', '100']):
            args = parse_args()
            assert args.count == 100
            assert args.key_type == 'ec'
            assert args.ec_curve == 'secp256r1'
            assert args.batch_size == 10000

    def test_parse_args_all_options(self):
        """Test parsing with all command line options."""
        test_args = [
            'generate_certificates.py',
            '--count', '500',
            '--root-validity', '365',
            '--intermediate-validity', '180',
            '--cert-validity', '90',
            '--key-type', 'rsa',
            '--ec-curve', 'secp384r1',
            '--rsa-key-size', '4096',
            '--output-dir', '/tmp/test',
            '--batch-size', '5000',
            '--cn-prefix', 'TestDevice-',
            '--country', 'CA',
            '--state', 'Ontario',
            '--locality', 'Toronto',
            '--org', 'Test Company',
            '--org-unit', 'Test Division'
        ]
        
        with patch('sys.argv', test_args):
            args = parse_args()
            assert args.count == 500
            assert args.root_validity == 365
            assert args.intermediate_validity == 180
            assert args.cert_validity == 90
            assert args.key_type == 'rsa'
            assert args.ec_curve == 'secp384r1'
            assert args.rsa_key_size == 4096
            assert args.output_dir == '/tmp/test'
            assert args.batch_size == 5000
            assert args.cn_prefix == 'TestDevice-'
            assert args.country == 'CA'
            assert args.state == 'Ontario'
            assert args.locality == 'Toronto'
            assert args.org == 'Test Company'
            assert args.org_unit == 'Test Division'

    def test_parse_args_invalid_key_type(self, capsys):
        """Test parsing with invalid key type."""
        with pytest.raises(SystemExit):
            with patch('sys.argv', ['generate_certificates.py', '--count', '100', '--key-type', 'invalid']):
                parse_args()
        
        # Capture and discard stdout/stderr to keep test output clean
        captured = capsys.readouterr()


class TestGenerateBatch:
    """Test batch generation function."""

    def test_generate_batch(self):
        """Test batch certificate generation."""
        # Create test certificates
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
        
        # Serialize certificates and key
        root_ca_ser = root_cert.public_bytes(encoding=serialization.Encoding.PEM)
        int_ca_ser = int_cert.public_bytes(encoding=serialization.Encoding.PEM)
        int_key_ser = int_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        
        # Create mock args
        args = MagicMock()
        args.cn_prefix = 'Device-'
        args.cert_validity = 30
        args.key_type = 'ec'
        args.ec_curve = 'secp256r1'
        args.rsa_key_size = 2048
        args.country = 'US'
        args.state = 'Washington'
        args.locality = 'Seattle'
        args.org = 'Test Corp'
        args.org_unit = 'IoT Division'
        
        # Generate batch
        results = generate_batch(0, 2, args, int_ca_ser, int_key_ser, root_ca_ser)
        
        assert len(results) == 2
        assert all(isinstance(cert, str) for cert in results)
        # Each result should be base64 encoded
        for cert in results:
            decoded = base64.b64decode(cert)
            assert b'-----BEGIN CERTIFICATE-----' in decoded


class TestMainFunction:
    """Test main function execution."""

    @patch('src.certificate_generator.generate_certificates.ProcessPoolExecutor')
    @patch('src.certificate_generator.generate_certificates.Path.mkdir')
    @patch('builtins.open')
    @patch('src.certificate_generator.generate_certificates.parse_args')
    def test_main_execution(self, mock_parse_args, mock_open, mock_mkdir, mock_executor, capsys):
        """Test main function execution flow."""
        # Mock arguments
        mock_args = MagicMock()
        mock_args.count = 100
        mock_args.batch_size = 50
        mock_args.output_dir = '/tmp/test'
        mock_args.key_type = 'ec'
        mock_args.ec_curve = 'secp256r1'
        mock_args.rsa_key_size = 2048
        mock_args.root_validity = 30
        mock_args.intermediate_validity = 30
        mock_args.cert_validity = 30
        mock_args.country = 'US'
        mock_args.state = 'Washington'
        mock_args.locality = 'Seattle'
        mock_args.org = 'Test Corp'
        mock_args.org_unit = 'IoT Division'
        mock_args.cn_prefix = 'Device-'
        mock_parse_args.return_value = mock_args
        
        # Mock executor
        mock_future = MagicMock()
        mock_future.result.return_value = ['cert1', 'cert2']
        mock_executor_instance = MagicMock()
        mock_executor_instance.__enter__.return_value = mock_executor_instance
        mock_executor_instance.submit.return_value = mock_future
        mock_executor.return_value = mock_executor_instance
        
        # Mock file operations
        mock_file = MagicMock()
        mock_open.return_value.__enter__.return_value = mock_file
        
        # Redirect tqdm output to prevent progress bar from showing in test output
        with patch('tqdm.tqdm', lambda x, **kwargs: x):
            main()
            
        # Capture and discard stdout/stderr to keep test output clean
        captured = capsys.readouterr()
            
        # Verify key operations were called
        mock_mkdir.assert_called()
        mock_executor_instance.submit.assert_called()
        mock_file.write.assert_called()
        
        # Verify print statements were captured
        assert 'Generating 100 certificates' in captured.out
        assert 'Successfully generated 100 certificates' in captured.out

    @patch('src.certificate_generator.generate_certificates.multiprocessing.cpu_count')
    @patch('src.certificate_generator.generate_certificates.parse_args')
    def test_worker_count_calculation(self, mock_parse_args, mock_cpu_count, capsys):
        """Test worker count calculation logic."""
        mock_cpu_count.return_value = 8
        
        # Create mock args with all required attributes
        mock_args = MagicMock()
        mock_args.count = 100
        mock_args.batch_size = 100  # Only 1 batch
        mock_args.output_dir = '/tmp/test'
        mock_args.key_type = 'ec'
        mock_args.ec_curve = 'secp256r1'
        mock_args.rsa_key_size = 2048
        mock_args.root_validity = 30
        mock_args.intermediate_validity = 30
        mock_args.cert_validity = 30
        mock_args.country = 'US'
        mock_args.state = 'Washington'
        mock_args.locality = 'Seattle'
        mock_args.org = 'Test Corp'
        mock_args.org_unit = 'IoT Division'
        mock_args.cn_prefix = 'Device-'
        mock_parse_args.return_value = mock_args
        
        with patch('src.certificate_generator.generate_certificates.ProcessPoolExecutor') as mock_executor, \
             patch('src.certificate_generator.generate_certificates.Path.mkdir'), \
             patch('builtins.open'):
            
            mock_executor_instance = MagicMock()
            mock_executor_instance.__enter__.return_value = mock_executor_instance
            mock_executor.return_value = mock_executor_instance
            
            # Redirect tqdm output to prevent progress bar from showing in test output
            with patch('tqdm.tqdm', lambda x, **kwargs: x):
                main()
            
            # Capture and discard stdout/stderr to keep test output clean
            captured = capsys.readouterr()
            
            # Should use min(cpu_count, num_batches) = min(8, 1) = 1
            mock_executor.assert_called_with(max_workers=1)

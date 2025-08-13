"""
Unit tests for Espressif provider throttling functionality.

Tests the integration of standardized throttling in the Espressif provider.
"""

import os
import pytest
from unittest.mock import patch, MagicMock, call
from boto3 import Session

# Set required environment variables before importing
os.environ['POWERTOOLS_IDEMPOTENCY_TABLE'] = 'test-idempotency-table'
os.environ['POWERTOOLS_IDEMPOTENCY_EXPIRY_SECONDS'] = '3600'

from src.provider_espressif.provider_espressif.main import invoke_export

ESPRESSIF_CERTIFICATE = """\"-----BEGIN CERTIFICATE-----
MIIDfDCCAmSgAwIBAgIUOL0c6TNOCR81dwfgSfPoiIVVzv4wDQYJKoZIhvcNAQEL
BQAwUzELMAkGA1UEBhMCSU4xCzAJBgNVBAgMAk1IMQ0wCwYDVQQHDARQdW5lMRIw
EAYDVQQKDAlFc3ByZXNzaWYxFDASBgNVBAMMC2VzcC10ZXN0LWNuMB4XDTI1MDQw
MzE0MzEwOVoXDTM1MDQwMTE0MzEwOVowezELMAkGA1UEBhMCSU4xCzAJBgNVBAgM
Ak1IMRowGAYDVQQKDBFFc3ByZXNzaWYgU3lzdGVtczEUMBIGA1UECwwLRXhwcmVz
c0xpbmsxLTArBgNVBAMMJGIxYzJjOTA3LWFkNTktNDBjNi05YTliLTMyYmFmZTE4
MDk5MjCCASIwDQYJKoZIhvcNAQEBBQADggEPADCCAQoCggEBAJaG8OVntGAODM9L
Sjt7bo5WjrAvAATls2bt9Zth9W7qoyTLCnUoFqvzsUaqHBs2pUbf0pd6Q4nN9CTO
JKSGWJex2mf31KiuQEyu1P5oBo9D1TBL0iEwuF8jFJLWMn3vmiYCC70ltNZ/PtTA
k/eNrSHXv0fbxcjj2qUMi06UZKsmy/YL0KVxYU9JPlfPoruX8upQIdLwHsX1ZCfu
0tjg1LRqw6TcJVxkEGDoGeoITrQDez+To7vusGdfAgA3zqvOjRq3ze4U8D457tu/
0P5hHT2gf70CX7XDnca9qH0g/ko/+u5iQWoYLVYowYdsq8a+dhu2dw91g+vrx0Vy
URcnWSsCAwEAAaMgMB4wDAYDVR0TAQH/BAIwADAOBgNVHQ8BAf8EBAMCBaAwDQYJ
KoZIhvcNAQELBQADggEBAAb397NXjFwUC5TmWpY6aB6MXN2XhGNTcDKfzsu7Y+BJ
kt6E/UlJ+mCO/iNc5KY40q3yIGPfC0GI1D9PgTJf3z7VYjqyvf3TF+SqPG03UA4X
dXbRdzOU9WAmrCx9RZcs7ndmJJou/JCwD+Eo2R7rQ1h2tmdw9xtnomslV6ZF+J21
YfM2Z/c8/pmKRrLhrghaHYInsZWqonFkGufqtGtVNETvF8gHJRHliNpt2sThZWBc
RBj/9TimKDIzBTUrYfjG78Fieqqsa6/wGU9nLDZX4y2L0BLko482iqUXGAt/AZCq
2wvK3TY1LT2gFm/LG7ZFYEca3j30k1UQ97kRiaPmePM=
-----END CERTIFICATE-----
\""""

class TestEspressifThrottling:
    """Test cases for Espressif provider throttling integration."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.queue_url = "https://sqs.us-east-1.amazonaws.com/123456789012/test-queue"
        self.session = MagicMock(spec=Session)
        self.config = {
            'bucket': 'test-bucket',
            'key': 'test-manifest.csv',
            'thing_type': 'TestThingType',
            'thing_group': 'TestThingGroup',
            'policy': 'TestPolicy'
        }
    
    @patch('src.provider_espressif.provider_espressif.main.s3_object_bytes')
    @patch('src.provider_espressif.provider_espressif.main.create_standardized_throttler')
    def test_throttler_initialization(self, mock_create_throttler, mock_s3_bytes):
        """Test that standardized throttler is properly initialized."""
        mock_throttler = MagicMock()
        mock_create_throttler.return_value = mock_throttler
        
        # Mock CSV data with 5 certificates
        csv_data = "MAC,cert\n" + "\n".join([
            f"AA:BB:CC:DD:EE:{i:02X},{ESPRESSIF_CERTIFICATE}" for i in range(5)
        ])
        mock_s3_bytes.return_value = csv_data.encode()
        
        invoke_export(self.config, self.queue_url, session=self.session)
        
        # Verify throttler was created
        mock_create_throttler.assert_called_once()
        
        # Verify throttler was used for batch sending
        assert mock_throttler.send_batch_with_throttling.call_count > 0
    
    @patch('src.provider_espressif.provider_espressif.main.s3_object_bytes')
    @patch('src.provider_espressif.provider_espressif.main.create_standardized_throttler')
    def test_batch_processing_with_throttling(self, mock_create_throttler, mock_s3_bytes):
        """Test batch processing uses standardized throttling."""
        mock_throttler = MagicMock()
        mock_throttler.send_batch_with_throttling.return_value = [{"successful": True}]
        mock_throttler.get_throttling_stats.return_value = {
            "total_batches_processed": 3,
            "throttling_enabled": True,
            "throttling_type": "batch_based"
        }
        mock_create_throttler.return_value = mock_throttler
        
        # Mock CSV data with 25 certificates (3 full batches of 10, 1 partial batch of 5)
        csv_data = "MAC,cert\n" + "\n".join([
            f"AA:BB:CC:DD:EE:{i:02X},{ESPRESSIF_CERTIFICATE}" for i in range(25)
        ])
        mock_s3_bytes.return_value = csv_data.encode()
        
        result = invoke_export(self.config, self.queue_url, session=self.session)
        
        # Should have processed 25 certificates
        assert result == 25
        
        # Should have called throttler for batches (2 full batches + 1 final batch)
        assert mock_throttler.send_batch_with_throttling.call_count == 3
        
        # Check that final batch was marked as such
        final_call = mock_throttler.send_batch_with_throttling.call_args_list[-1]
        assert final_call[1]['is_final_batch'] is True
        
        # Verify throttling stats were retrieved
        mock_throttler.get_throttling_stats.assert_called_once()
    
    @patch('src.provider_espressif.provider_espressif.main.s3_object_bytes')
    @patch('src.provider_espressif.provider_espressif.main.create_standardized_throttler')
    def test_single_batch_processing(self, mock_create_throttler, mock_s3_bytes):
        """Test processing with only one batch."""
        mock_throttler = MagicMock()
        mock_throttler.send_batch_with_throttling.return_value = [{"successful": True}]
        mock_throttler.get_throttling_stats.return_value = {
            "total_batches_processed": 1,
            "throttling_enabled": True
        }
        mock_create_throttler.return_value = mock_throttler
        
        # Mock CSV data with 5 certificates (less than batch size)
        csv_data = "MAC,cert\n" + "\n".join([
            f"AA:BB:CC:DD:EE:{i:02X},{ESPRESSIF_CERTIFICATE}" for i in range(5)
        ])
        mock_s3_bytes.return_value = csv_data.encode()
        
        result = invoke_export(self.config, self.queue_url, session=self.session)
        
        # Should have processed 5 certificates
        assert result == 5
        
        # Should have called throttler once for final batch
        mock_throttler.send_batch_with_throttling.assert_called_once()
        
        # Check that it was marked as final batch
        call_args = mock_throttler.send_batch_with_throttling.call_args
        assert call_args[1]['is_final_batch'] is True
    
    @patch('src.provider_espressif.provider_espressif.main.s3_object_bytes')
    @patch('src.provider_espressif.provider_espressif.main.create_standardized_throttler')
    def test_empty_manifest_handling(self, mock_create_throttler, mock_s3_bytes):
        """Test handling of empty manifest."""
        mock_throttler = MagicMock()
        mock_throttler.get_throttling_stats.return_value = {
            "total_batches_processed": 0,
            "throttling_enabled": True
        }
        mock_create_throttler.return_value = mock_throttler
        
        # Mock empty CSV data
        csv_data = "MAC,cert\n"
        mock_s3_bytes.return_value = csv_data.encode()
        
        result = invoke_export(self.config, self.queue_url, session=self.session)
        
        # Should have processed 0 certificates
        assert result == 0
        
        # Should not have called throttler for sending
        mock_throttler.send_batch_with_throttling.assert_not_called()
        
        # Should still get throttling stats
        mock_throttler.get_throttling_stats.assert_called_once()
    
    @patch('src.provider_espressif.provider_espressif.main.s3_object_bytes')
    @patch('src.provider_espressif.provider_espressif.main.create_standardized_throttler')
    def test_certificate_data_format(self, mock_create_throttler, mock_s3_bytes):
        """Test that certificate data is properly formatted for throttler."""
        mock_throttler = MagicMock()
        mock_throttler.send_batch_with_throttling.return_value = [{"successful": True}]
        mock_create_throttler.return_value = mock_throttler
        
        # Mock CSV data with specific certificate content
        csv_data = f"MAC,cert\nAA:BB:CC:DD:EE:FF,{ESPRESSIF_CERTIFICATE}"
        mock_s3_bytes.return_value = csv_data.encode()
        
        invoke_export(self.config, self.queue_url, session=self.session)
        
        # Verify the message format sent to throttler
        call_args = mock_throttler.send_batch_with_throttling.call_args[0]
        batch_messages = call_args[0]
        
        assert len(batch_messages) == 1
        message = batch_messages[0]
        
        # Check message structure
        assert 'thing' in message
        assert 'certificate' in message
        assert 'thing_type' in message
        assert 'thing_group' in message
        assert 'policy' in message
        
        # Check specific values
        assert message['thing'] == 'AA:BB:CC:DD:EE:FF'
        assert message['thing_type'] == 'TestThingType'
        assert message['thing_group'] == 'TestThingGroup'
        assert message['policy'] == 'TestPolicy'
        
        # Certificate should be base64 encoded
        import base64
        from ast import literal_eval

        decoded_cert = base64.b64decode(literal_eval(message['certificate'])).decode('ascii')

        assert ('"' + decoded_cert + '"') == ESPRESSIF_CERTIFICATE

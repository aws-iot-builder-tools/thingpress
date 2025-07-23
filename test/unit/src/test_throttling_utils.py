"""
Unit tests for standardized throttling utilities.

Tests the ThrottlingConfig, StandardizedThrottler, and related functionality
to ensure consistent throttling behavior across all vendor providers.
"""

import os
import time
import pytest
from unittest.mock import patch, MagicMock, call
from boto3 import Session

from src.layer_utils.layer_utils.throttling_utils import (
    ThrottlingConfig, StandardizedThrottler, create_standardized_throttler
)


class TestThrottlingConfig:
    """Test cases for ThrottlingConfig class."""
    
    def test_default_configuration(self):
        """Test default throttling configuration values."""
        config = ThrottlingConfig()
        
        assert config.auto_throttling_enabled is True
        assert config.throttling_base_delay == 30
        assert config.throttling_batch_interval == 3
        assert config.max_queue_depth == 1000
        assert config.use_adaptive_throttling is False
    
    @patch.dict(os.environ, {
        'AUTO_THROTTLING_ENABLED': 'false',
        'THROTTLING_BASE_DELAY': '60',
        'THROTTLING_BATCH_INTERVAL': '5',
        'MAX_QUEUE_DEPTH': '2000',
        'USE_ADAPTIVE_THROTTLING': 'true'
    })
    def test_environment_configuration(self):
        """Test throttling configuration from environment variables."""
        config = ThrottlingConfig()
        
        assert config.auto_throttling_enabled is False
        assert config.throttling_base_delay == 60
        assert config.throttling_batch_interval == 5
        assert config.max_queue_depth == 2000
        assert config.use_adaptive_throttling is True


class TestStandardizedThrottler:
    """Test cases for StandardizedThrottler class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.config = ThrottlingConfig()
        self.throttler = StandardizedThrottler(self.config)
        self.queue_url = "https://sqs.us-east-1.amazonaws.com/123456789012/test-queue"
        self.session = MagicMock(spec=Session)
    
    def test_initialization(self):
        """Test throttler initialization."""
        assert self.throttler.config == self.config
        assert self.throttler.batch_count == 0
    
    def test_should_throttle_enabled(self):
        """Test throttling decision when enabled."""
        self.config.auto_throttling_enabled = True
        self.config.throttling_batch_interval = 3
        
        # First two batches should not throttle
        self.throttler.batch_count = 1
        assert not self.throttler.should_throttle()
        
        self.throttler.batch_count = 2
        assert not self.throttler.should_throttle()
        
        # Third batch should throttle
        self.throttler.batch_count = 3
        assert self.throttler.should_throttle()
        
        # Sixth batch should throttle
        self.throttler.batch_count = 6
        assert self.throttler.should_throttle()
    
    def test_should_throttle_disabled(self):
        """Test throttling decision when disabled."""
        self.config.auto_throttling_enabled = False
        self.throttler.batch_count = 3
        
        assert not self.throttler.should_throttle()
    
    @patch('time.sleep')
    def test_apply_batch_throttling_enabled(self, mock_sleep):
        """Test batch throttling when enabled."""
        self.config.auto_throttling_enabled = True
        self.config.throttling_batch_interval = 3
        self.config.throttling_base_delay = 30
        self.throttler.batch_count = 3
        
        with patch('src.layer_utils.layer_utils.throttling_utils.logger') as mock_logger:
            self.throttler.apply_batch_throttling()
        
        mock_sleep.assert_called_once_with(30)
        mock_logger.info.assert_called_once()
        
        # Check log message content
        log_call = mock_logger.info.call_args[0][0]
        assert log_call["message"] == "Applying throttling delay"
        assert log_call["batch_number"] == 3
        assert log_call["delay_seconds"] == 30
        assert log_call["throttling_interval"] == 3
        assert log_call["throttling_type"] == "batch_based"
    
    @patch('time.sleep')
    def test_apply_batch_throttling_disabled(self, mock_sleep):
        """Test batch throttling when disabled."""
        self.config.auto_throttling_enabled = False
        self.throttler.batch_count = 3
        
        self.throttler.apply_batch_throttling()
        
        mock_sleep.assert_not_called()
    
    @patch('time.sleep')
    def test_apply_batch_throttling_wrong_interval(self, mock_sleep):
        """Test batch throttling when not at throttling interval."""
        self.config.auto_throttling_enabled = True
        self.config.throttling_batch_interval = 3
        self.throttler.batch_count = 2
        
        self.throttler.apply_batch_throttling()
        
        mock_sleep.assert_not_called()
    
    @patch('time.sleep')
    @patch('src.layer_utils.layer_utils.throttling_utils.get_queue_depth')
    @patch('src.layer_utils.layer_utils.throttling_utils.calculate_optimal_delay')
    def test_apply_adaptive_throttling_enabled(self, mock_calc_delay, mock_get_depth, mock_sleep):
        """Test adaptive throttling when enabled."""
        self.config.auto_throttling_enabled = True
        self.config.use_adaptive_throttling = True
        self.config.throttling_base_delay = 30
        
        mock_get_depth.return_value = {'total': 1500}
        mock_calc_delay.return_value = 60
        
        with patch('src.layer_utils.layer_utils.throttling_utils.logger') as mock_logger:
            self.throttler.apply_adaptive_throttling(self.queue_url, self.session)
        
        mock_get_depth.assert_called_once_with(self.queue_url, self.session)
        mock_calc_delay.assert_called_once_with(1500, 30)
        mock_sleep.assert_called_once_with(60)
        
        # Check log messages
        assert mock_logger.info.call_count == 2
    
    @patch('time.sleep')
    @patch('src.layer_utils.layer_utils.throttling_utils.get_queue_depth')
    def test_apply_adaptive_throttling_fallback(self, mock_get_depth, mock_sleep):
        """Test adaptive throttling fallback to batch throttling on error."""
        self.config.auto_throttling_enabled = True
        self.config.use_adaptive_throttling = True
        self.config.throttling_batch_interval = 3
        self.throttler.batch_count = 3
        
        mock_get_depth.side_effect = Exception("Queue error")
        
        with patch('src.layer_utils.layer_utils.throttling_utils.logger') as mock_logger:
            self.throttler.apply_adaptive_throttling(self.queue_url, self.session)
        
        # Should have logged warning and applied batch throttling
        mock_logger.warning.assert_called_once()
        mock_sleep.assert_called_once_with(30)  # batch throttling delay
    
    @patch('src.layer_utils.layer_utils.throttling_utils.send_sqs_message_batch_with_retry')
    def test_send_batch_with_throttling_batch_mode(self, mock_send):
        """Test sending batch with batch-based throttling."""
        self.config.auto_throttling_enabled = True
        self.config.use_adaptive_throttling = False
        self.config.throttling_batch_interval = 3
        
        batch_messages = [{"test": "message1"}, {"test": "message2"}]
        mock_send.return_value = [{"successful": True}]
        
        with patch.object(self.throttler, 'apply_batch_throttling') as mock_batch_throttle:
            result = self.throttler.send_batch_with_throttling(
                batch_messages, self.queue_url, self.session
            )
        
        assert self.throttler.batch_count == 1
        mock_batch_throttle.assert_called_once()
        mock_send.assert_called_once_with(batch_messages, self.queue_url, self.session)
        assert result == [{"successful": True}]
    
    @patch('src.layer_utils.layer_utils.throttling_utils.send_sqs_message_batch_with_retry')
    def test_send_batch_with_throttling_adaptive_mode(self, mock_send):
        """Test sending batch with adaptive throttling."""
        self.config.auto_throttling_enabled = True
        self.config.use_adaptive_throttling = True
        
        batch_messages = [{"test": "message1"}, {"test": "message2"}]
        mock_send.return_value = [{"successful": True}]
        
        with patch.object(self.throttler, 'apply_adaptive_throttling') as mock_adaptive_throttle:
            result = self.throttler.send_batch_with_throttling(
                batch_messages, self.queue_url, self.session, is_final_batch=True
            )
        
        assert self.throttler.batch_count == 1
        mock_adaptive_throttle.assert_called_once_with(self.queue_url, self.session)
        mock_send.assert_called_once_with(batch_messages, self.queue_url, self.session)
        assert result == [{"successful": True}]
    
    def test_get_throttling_stats(self):
        """Test getting throttling statistics."""
        self.throttler.batch_count = 5
        
        stats = self.throttler.get_throttling_stats()
        
        expected_stats = {
            "total_batches_processed": 5,
            "throttling_enabled": True,
            "throttling_type": "batch_based",
            "base_delay": 30,
            "batch_interval": 3,
            "max_queue_depth": 1000
        }
        
        assert stats == expected_stats
    
    def test_get_throttling_stats_adaptive(self):
        """Test getting throttling statistics for adaptive mode."""
        self.config.use_adaptive_throttling = True
        self.throttler.batch_count = 10
        
        stats = self.throttler.get_throttling_stats()
        
        assert stats["throttling_type"] == "adaptive"
        assert stats["total_batches_processed"] == 10


class TestCreateStandardizedThrottler:
    """Test cases for the factory function."""
    
    def test_create_standardized_throttler(self):
        """Test factory function creates throttler with environment config."""
        throttler = create_standardized_throttler()
        
        assert isinstance(throttler, StandardizedThrottler)
        assert isinstance(throttler.config, ThrottlingConfig)
        assert throttler.batch_count == 0
    
    @patch.dict(os.environ, {
        'AUTO_THROTTLING_ENABLED': 'false',
        'THROTTLING_BASE_DELAY': '45'
    })
    def test_create_standardized_throttler_with_env(self):
        """Test factory function respects environment variables."""
        throttler = create_standardized_throttler()
        
        assert throttler.config.auto_throttling_enabled is False
        assert throttler.config.throttling_base_delay == 45


class TestIntegrationScenarios:
    """Integration test scenarios for realistic usage patterns."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.throttler = create_standardized_throttler()
        self.queue_url = "https://sqs.us-east-1.amazonaws.com/123456789012/test-queue"
        self.session = MagicMock(spec=Session)
    
    @patch('src.layer_utils.layer_utils.throttling_utils.send_sqs_message_batch_with_retry')
    @patch('time.sleep')
    def test_multiple_batch_processing(self, mock_sleep, mock_send):
        """Test processing multiple batches with throttling."""
        mock_send.return_value = [{"successful": True}]
        
        # Process 10 batches (should throttle on batches 3, 6, 9)
        for i in range(10):
            batch_messages = [{"batch": i, "message": j} for j in range(5)]
            self.throttler.send_batch_with_throttling(batch_messages, self.queue_url, self.session)
        
        # Should have called sleep 3 times (batches 3, 6, 9)
        assert mock_sleep.call_count == 3
        assert mock_send.call_count == 10
        
        # Verify sleep was called with correct delay
        for call_args in mock_sleep.call_args_list:
            assert call_args[0][0] == 30  # default base delay
    
    @patch('src.layer_utils.layer_utils.throttling_utils.send_sqs_message_batch_with_retry')
    @patch.dict(os.environ, {'AUTO_THROTTLING_ENABLED': 'false'})
    def test_throttling_disabled_scenario(self, mock_send):
        """Test processing when throttling is disabled."""
        throttler = create_standardized_throttler()
        mock_send.return_value = [{"successful": True}]
        
        with patch('time.sleep') as mock_sleep:
            # Process 5 batches
            for i in range(5):
                batch_messages = [{"batch": i}]
                throttler.send_batch_with_throttling(batch_messages, self.queue_url, self.session)
        
        # No throttling should occur
        mock_sleep.assert_not_called()
        assert mock_send.call_count == 5
        
        stats = throttler.get_throttling_stats()
        assert stats["throttling_enabled"] is False
        assert stats["total_batches_processed"] == 5

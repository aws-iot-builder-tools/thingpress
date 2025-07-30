#!/usr/bin/env python3
"""
Test for __main__ block execution in certificate generator.
"""

import pytest
from unittest.mock import patch, MagicMock


class TestMainBlockExecution:
    """Test __main__ block execution."""

    @patch('generate_certificates.time.time')
    @patch('generate_certificates.main')
    @patch('builtins.print')
    def test_main_block_execution(self, mock_print, mock_main, mock_time):
        """Test __main__ block execution with timing."""
        mock_time.side_effect = [100.0, 105.5]  # start_time, end_time
        
        # Simulate the __main__ block execution
        with patch('generate_certificates.__name__', '__main__'):
            # Execute the __main__ block code directly
            start_time = mock_time()
            mock_main()
            elapsed_time = mock_time() - start_time
            mock_print(f"Total execution time: {elapsed_time:.2f} seconds")
        
        mock_main.assert_called_once()
        mock_print.assert_called_with('Total execution time: 5.50 seconds')
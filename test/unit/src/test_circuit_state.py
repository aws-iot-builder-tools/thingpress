"""
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

Unit tests for circuit_state.py
"""

import math
import time
import logging
import unittest
from unittest.mock import patch, MagicMock
import pytest

# Import the module directly
from src.layer_utils.circuit_state import (
    CircuitState,
    circuit_is_open,
    record_failure,
    reset_circuit,
    CircuitOpenError,
    with_circuit_breaker,
    _circuit_states
)

# Create a test logger to capture log messages
test_logger = logging.getLogger('test_logger')

class TestCircuitState(unittest.TestCase):
    """Test cases for CircuitState class"""

    def setUp(self):
        """Reset circuit states before each test"""
        _circuit_states.clear()

    def test_circuit_state_initialization(self):
        """Test that CircuitState initializes with correct default values"""
        state = CircuitState()
        self.assertFalse(state.is_open)
        self.assertEqual(state.failure_count, 0)
        self.assertEqual(state.last_failure_time, 0)
        self.assertEqual(state.threshold, 5)
        self.assertEqual(state.timeout, 60)

class TestCircuitIsOpen(unittest.TestCase):
    """Test cases for circuit_is_open function"""

    def setUp(self):
        """Reset circuit states before each test"""
        _circuit_states.clear()

    def test_new_operation_returns_false(self):
        """Test that a new operation returns False (circuit closed)"""
        self.assertFalse(circuit_is_open("test_operation"))
        # Verify the operation was added to circuit states
        self.assertIn("test_operation", _circuit_states)

    def test_open_circuit_returns_true(self):
        """Test that an open circuit returns True"""
        # Set up an open circuit
        _circuit_states["test_operation"] = CircuitState()
        _circuit_states["test_operation"].is_open = True
        _circuit_states["test_operation"].last_failure_time = time.time()

        # Verify circuit is reported as open
        self.assertTrue(circuit_is_open("test_operation"))

    #@pytest.mark.skip(reason="Fails when run as part of the full test suite")
    def test_half_open_after_timeout(self):
        """Test that circuit moves to half-open state after timeout"""
        # Set up an open circuit with old timestamp
        _circuit_states["test_operation"] = CircuitState()
        _circuit_states["test_operation"].is_open = True
        _circuit_states["test_operation"].last_failure_time = time.time() - 120

        # Verify circuit is reported as closed (half-open state)
        self.assertFalse(circuit_is_open("test_operation"))

class TestRecordFailure(unittest.TestCase):
    """Test cases for record_failure function"""

    def setUp(self):
        """Reset circuit states before each test"""
        _circuit_states.clear()

    def test_new_operation_creates_state(self):
        """Test that recording a failure for a new operation creates a state"""
        record_failure("test_operation")
        self.assertIn("test_operation", _circuit_states)
        self.assertEqual(_circuit_states["test_operation"].failure_count, 1)

    def test_increments_failure_count(self):
        """Test that recording a failure increments the failure count"""
        # Set up existing circuit
        _circuit_states["test_operation"] = CircuitState()
        _circuit_states["test_operation"].failure_count = 2

        # Record another failure
        record_failure("test_operation")
        self.assertEqual(_circuit_states["test_operation"].failure_count, 3)

    # @pytest.mark.skip(reason="Fails when run as part of the full test suite")
    def test_updates_last_failure_time(self):
        """Test that recording a failure updates the last failure time"""
        # Set up existing circuit with old timestamp
        _circuit_states["test_operation"] = CircuitState()
        _circuit_states["test_operation"].last_failure_time = 0

        # Record a failure
        before_time = time.time()
        record_failure("test_operation")
        after_time = time.time()

        # Verify the last_failure_time was updated to a recent timestamp
        self.assertGreaterEqual(_circuit_states["test_operation"].last_failure_time, before_time)
        self.assertLessEqual(_circuit_states["test_operation"].last_failure_time, after_time)

    def test_opens_circuit_at_threshold(self):
        """Test that circuit opens when failure count reaches threshold"""
        # Set up existing circuit near threshold
        _circuit_states["test_operation"] = CircuitState()
        _circuit_states["test_operation"].failure_count = 4
        _circuit_states["test_operation"].threshold = 5

        # Record another failure to reach threshold
        record_failure("test_operation")

        # Verify the circuit is open
        self.assertTrue(_circuit_states["test_operation"].is_open)

class TestResetCircuit(unittest.TestCase):
    """Test cases for reset_circuit function"""

    def setUp(self):
        """Reset circuit states before each test"""
        _circuit_states.clear()

    def test_reset_nonexistent_circuit(self):
        """Test that resetting a nonexistent circuit does nothing"""
        # This should not raise an exception
        reset_circuit("nonexistent_operation")

    def test_reset_open_circuit(self):
        """Test that resetting an open circuit closes it and resets failure count"""
        # Set up an open circuit
        _circuit_states["test_operation"] = CircuitState()
        _circuit_states["test_operation"].is_open = True
        _circuit_states["test_operation"].failure_count = 10

        # Reset the circuit
        reset_circuit("test_operation")

        # Verify the circuit is reset
        self.assertFalse(_circuit_states["test_operation"].is_open)
        self.assertEqual(_circuit_states["test_operation"].failure_count, 0)

    def test_reset_circuit_with_failures(self):
        """Test that resetting a circuit with failures resets the failure count"""
        # Set up a circuit with failures but not open
        _circuit_states["test_operation"] = CircuitState()
        _circuit_states["test_operation"].is_open = False
        _circuit_states["test_operation"].failure_count = 3

        # Reset the circuit
        reset_circuit("test_operation")

        # Verify the circuit is reset
        self.assertFalse(_circuit_states["test_operation"].is_open)
        self.assertEqual(_circuit_states["test_operation"].failure_count, 0)

    def test_reset_clean_circuit_no_log(self):
        """Test that resetting a clean circuit doesn't log anything"""
        # Set up a clean circuit
        _circuit_states["test_operation"] = CircuitState()
        _circuit_states["test_operation"].is_open = False
        _circuit_states["test_operation"].failure_count = 0

        # Create a test logger with a mock handler
        mock_logger = logging.getLogger('test_logger')
        mock_logger.setLevel(logging.INFO)
        mock_handler = MagicMock()
        mock_logger.addHandler(mock_handler)

        # Replace the logger in the module
        with patch('src.layer_utils.circuit_state.logger', test_logger):
            # Reset the circuit
            reset_circuit("test_operation")
            self.assertFalse(_circuit_states["test_operation"].is_open)
            self.assertEqual(_circuit_states["test_operation"].failure_count, 0)
            # Verify no log message (handler not called)
            mock_handler.handle.assert_not_called()

class TestCircuitBreakerDecorator(unittest.TestCase):
    """Test cases for with_circuit_breaker decorator"""

    def setUp(self):
        """Reset circuit states before each test"""
        _circuit_states.clear()

    def test_successful_function_call(self):
        """Test that a successful function call works normally and resets circuit"""
        # Define a test function
        @with_circuit_breaker("test_operation")
        def test_function():
            return "success"

        # Call the function
        result = test_function()
        self.assertEqual(result, "success")

        # Verify circuit state
        self.assertIn("test_operation", _circuit_states)
        self.assertEqual(_circuit_states["test_operation"].failure_count, 0)

    def test_function_with_exception(self):
        """Test that an exception is recorded and re-raised"""
        # Define a test function that raises an exception
        @with_circuit_breaker("test_operation")
        def test_function():
            raise ValueError("test error")

        # Call the function
        with self.assertRaises(ValueError):
            test_function()

        # Verify circuit state
        self.assertIn("test_operation", _circuit_states)
        self.assertEqual(_circuit_states["test_operation"].failure_count, 1)

    def test_open_circuit_raises_error(self):
        """Test that an open circuit raises CircuitOpenError"""
        # Set up an open circuit
        _circuit_states["test_operation"] = CircuitState()
        _circuit_states["test_operation"].is_open = True
        _circuit_states["test_operation"].last_failure_time = int(time.time())

        # Define a test function
        @with_circuit_breaker("test_operation")
        def test_function():
            return "success"

        # Call the function
        with self.assertRaises(CircuitOpenError):
            test_function()

    def test_open_circuit_with_fallback(self):
        """Test that an open circuit uses fallback function if provided"""
        # Set up an open circuit
        _circuit_states["test_operation"] = CircuitState()
        _circuit_states["test_operation"].is_open = True
        _circuit_states["test_operation"].last_failure_time = int(time.time())

        # Define a fallback function
        def fallback_function():
            return "fallback"

        # Define a test function with fallback
        @with_circuit_breaker("test_operation", fallback_function=fallback_function)
        def test_function():
            return "success"

        # Call the function
        result = test_function()
        self.assertEqual(result, "fallback")

    def test_preserves_function_metadata(self):
        """Test that the decorator preserves function metadata"""
        # Define a test function with docstring and name
        @with_circuit_breaker("test_operation")
        def test_function():
            """Test docstring"""
            return "success"

        self.assertEqual(test_function.__name__, "test_function")
        self.assertEqual(test_function.__doc__, "Test docstring")

class TestIntegration(unittest.TestCase):
    """Integration tests for circuit breaker pattern"""

    def setUp(self):
        """Reset circuit states before each test"""
        _circuit_states.clear()

    #@pytest.mark.skip(reason="Fails when run as part of the full test suite")
    def test_full_circuit_lifecycle(self):
        """Test the full lifecycle of a circuit breaker"""
        operation_name = "test_full_lifecycle"

        # Define a test function
        @with_circuit_breaker(operation_name)
        def test_function(should_fail=False):
            if should_fail:
                raise ValueError("test error")
            return "success"

        # 1. Initial successful call
        result = test_function()
        self.assertEqual(result, "success")
        self.assertIn(operation_name, _circuit_states)
        self.assertEqual(_circuit_states[operation_name].failure_count, 0)

        # 2. Record failures up to threshold
        for _ in range(5):
            with self.assertRaises(ValueError):
                test_function(should_fail=True)

        # 3. Verify circuit is open
        self.assertTrue(_circuit_states[operation_name].is_open)

        # 4. Verify next call fails fast with CircuitOpenError
        with self.assertRaises(CircuitOpenError):
            test_function()

        # 5. Simulate timeout and half-open state
        _circuit_states[operation_name].last_failure_time = time.time() - 120  # 2 minutes ago

        # 6. Next call should go through (half-open state)
        result = test_function()
        self.assertEqual(result, "success")

        # 7. Verify circuit is reset
        self.assertFalse(_circuit_states[operation_name].is_open)
        self.assertEqual(_circuit_states[operation_name].failure_count, 0)

if __name__ == '__main__':
    unittest.main()

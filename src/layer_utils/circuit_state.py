"""
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

Circuit breaker pattern implementation for AWS API calls
Please see the following url for conceptual overview
https://martinfowler.com/bliki/CircuitBreaker.html
"""
import time
import logging
from threading import Lock
from functools import wraps

# Set up logging
logger = logging.getLogger()
logger.setLevel("INFO")

# Circuit breaker state storage
_circuit_states : dict = {}
_circuit_lock : Lock = Lock()

class CircuitState:
    """
    Represents the state of a circuit breaker for a specific operation.
    
    Attributes:
        is_open (bool): Whether the circuit is currently open (failing fast)
        failure_count (int): Number of consecutive failures
        last_failure_time (float): Timestamp of the last failure
        threshold (int): Number of failures before opening the circuit
        timeout (int): Seconds to wait before trying again (half-open state)
    """
    def __init__(self):
        self.is_open : bool = False
        self.failure_count : int = 0
        self.last_failure_time : float = 0.0
        self.threshold : int = 5  # Number of failures before opening
        self.timeout : int = 60   # Seconds to wait before trying again

def circuit_is_open(operation_name: str):
    """
    Check if the circuit is open for a specific operation
    
    Args:
        operation_name (str): The name of the operation to check
        
    Returns:
        bool: True if the circuit is open and requests should fail fast
    """
    with _circuit_lock:
        if operation_name not in _circuit_states:
            _circuit_states[operation_name] = CircuitState()

        circuit = _circuit_states[operation_name]

        # If circuit is open, check if timeout has elapsed to try again
        if circuit.is_open is True:
            if time.time() - circuit.last_failure_time > circuit.timeout:
                logger.info("Circuit for %s moving to half-open state", operation_name)
                circuit.is_open = False
                return False
            return True
        return False

# Move to half-open state by allowing one request through

def record_failure(operation_name: str):
    """
    Record a failure for the circuit breaker
    
    Args:
        operation_name (str): The name of the operation that failed
    """
    with _circuit_lock:
        if operation_name not in _circuit_states:
            _circuit_states[operation_name] = CircuitState()

        circuit = _circuit_states[operation_name]
        circuit.failure_count += 1
        circuit.last_failure_time = time.time()

        # Open the circuit if we exceed the threshold
        if circuit.failure_count >= circuit.threshold:
            circuit.is_open = True
            logger.warning("Circuit breaker opened for %s after %i failures",
                           operation_name, circuit.threshold)

def reset_circuit(operation_name):
    """
    Reset the circuit after a successful operation
    
    Args:
        operation_name (str): The name of the operation that succeeded
    """
    with _circuit_lock:
        if operation_name not in _circuit_states:
            return

        circuit = _circuit_states[operation_name]
        if circuit.is_open or circuit.failure_count > 0:
            logger.info("Circuit for %s reset after successful operation", operation_name)
        circuit.is_open = False
        circuit.failure_count = 0

class CircuitOpenError(Exception):
    """Exception raised when a circuit is open"""
    pass

def with_circuit_breaker(operation_name, fallback_function=None):
    """
    Decorator to apply circuit breaker pattern to a function
    
    Args:
        operation_name (str): Name of the operation for the circuit breaker
        fallback_function (callable, optional): Function to call when circuit is open
        
    Example:
        @with_circuit_breaker('get_thing_group')
        def get_thing_group_arn(thing_group_name):
            # Implementation
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if circuit_is_open(operation_name):
                logger.warning("Circuit breaker open for %s, failing fast", operation_name)
                if fallback_function:
                    return fallback_function(*args, **kwargs)
                raise CircuitOpenError(f"Circuit breaker open for {operation_name}")

            try:
                result = func(*args, **kwargs)
                reset_circuit(operation_name)
                return result
            except Exception as e:
                record_failure(operation_name)
                raise

        return wrapper
    return decorator

def clear_circuits():
    """ Clears all circuits """
    _circuit_states.clear()

"""
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

Configure pytest environment
"""
import os
import sys
from pathlib import Path
import pytest

# Set up test environment variables at module level (before imports)
# AWS credentials for moto
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
os.environ["AWS_REGION"] = "us-east-1"
os.environ["AWS_ACCESS_KEY_ID"] = "testing"
os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
os.environ["AWS_SECURITY_TOKEN"] = "testing"
os.environ["AWS_SESSION_TOKEN"] = "testing"

# Powertools configuration for tests
os.environ["POWERTOOLS_IDEMPOTENCY_TABLE"] = "test-idempotency-table"
os.environ["POWERTOOLS_IDEMPOTENCY_EXPIRY_SECONDS"] = "3600"

# Disable throttling for tests to prevent hanging
os.environ["AUTO_THROTTLING_ENABLED"] = "false"
os.environ["USE_ADAPTIVE_THROTTLING"] = "false"
os.environ["THROTTLING_BASE_DELAY"] = "0"
os.environ["THROTTLING_BATCH_INTERVAL"] = "1"

# Add the project root directory to the Python path
project_root = Path(__file__).parent.parent.parent.parent
print("\nproject_root (conftest.py): ", str(project_root))
sys.path.insert(0, str(project_root))

# Add specific module directories to the Python path
# This makes modules directly importable in tests without relative imports
module_paths = [
    # Add paths to specific modules
    os.path.join(project_root, "src", "layer_utils", "layer_utils"),
    os.path.join(project_root, "src", "bulk_importer"),
    os.path.join(project_root, "src", "product_verifier"),
    os.path.join(project_root, "src", "provider_espressif"),
    os.path.join(project_root, "src", "provider_generated", "provider_generated"),
    os.path.join(project_root, "src", "provider_infineon", "provider_infineon"),
    os.path.join(project_root, "src", "provider_microchip", "provider_microchip"),
    os.path.join(project_root, "src", "certificate_generator"),
]

# Add each module path to sys.path
for path in module_paths:
    if path not in sys.path and os.path.exists(path):
        sys.path.insert(0, path)

# Create module aliases for compatibility
try:
    # Create aliases for common modules
    # For example, make src.layer_utils.aws_utils available as just aws_utils
    import src.layer_utils.aws_utils
    sys.modules['aws_utils'] = sys.modules['src.layer_utils.aws_utils']

    import src.layer_utils.cert_utils
    sys.modules['cert_utils'] = sys.modules['src.layer_utils.cert_utils']
except ImportError:
    # Handle case where modules aren't found
    pass

# Reset circuit state before each test
@pytest.fixture(autouse=True)
def reset_circuit_state(request):
    """Reset circuit state before each test"""
    # Skip for aws_utils tests
    if 'test_aws_utils' in request.node.name:
        yield
        return
        
    # Reset circuit state for other tests
    try:
        from src.layer_utils.circuit_state import _circuit_states
        _circuit_states.clear()
    except ImportError:
        pass
        
    yield

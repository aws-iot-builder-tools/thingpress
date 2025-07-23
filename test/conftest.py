"""
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

Configure pytest environment
"""
import os
import sys
from pathlib import Path
import pytest

# Add the project root directory to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Add specific module directories to the Python path
# This makes modules directly importable in tests without relative imports
module_paths = [
    # Add paths to specific modules
    os.path.join(project_root, "src", "layer_utils"),
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

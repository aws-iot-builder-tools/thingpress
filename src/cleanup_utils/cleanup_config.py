"""
Configuration and constants for Thingpress cleanup operations
"""

from dataclasses import dataclass
from typing import List, Dict, Optional
import os


@dataclass
class CleanupConfig:
    """Configuration for Thingpress cleanup operations"""
    
    # AWS Configuration
    region: str = "us-east-1"
    profile_name: Optional[str] = None
    
    # Resource Identification
    resource_tag_key: str = "created-by"
    resource_tag_value: str = "thingpress"
    stack_name_prefix: str = "thingpress"
    
    # Test-specific patterns for IoT things
    test_thing_patterns: List[str] = None
    
    # Cleanup Behavior
    dry_run: bool = False
    cleanup_iot_resources: bool = True
    cleanup_s3_resources: bool = True
    cleanup_cloudformation_stacks: bool = True
    verify_cleanup: bool = True
    
    # Timing
    verification_wait_seconds: int = 30
    stack_deletion_timeout_minutes: int = 30
    
    # Logging
    verbose: bool = False
    
    def __post_init__(self):
        """Initialize default values after dataclass creation"""
        if self.test_thing_patterns is None:
            self.test_thing_patterns = [
                '0123',      # Microchip test certificates
                'test_',     # Generic test things
                '_e2e',      # End-to-end test suffix
            ]
        
        # Override from environment variables if present
        self.region = os.getenv('AWS_REGION', self.region)
        self.profile_name = os.getenv('AWS_PROFILE', self.profile_name)
        self.stack_name_prefix = os.getenv('STACK_NAME_PREFIX', self.stack_name_prefix)
        self.dry_run = os.getenv('DRY_RUN', str(self.dry_run)).lower() == 'true'
    
    @classmethod
    def for_integration_tests(cls, stack_name: str = None, region: str = None) -> 'CleanupConfig':
        """Create configuration optimized for integration tests"""
        return cls(
            region=region or os.getenv('AWS_REGION', 'us-east-1'),
            stack_name_prefix=stack_name or os.getenv('THINGPRESS_STACK_NAME', 'thingpress'),
            cleanup_cloudformation_stacks=False,  # Don't delete stacks during tests
            verification_wait_seconds=5,  # Faster verification for tests
            verbose=True,
        )
    
    @classmethod
    def for_standalone_cleanup(cls, stack_prefix: str = None, region: str = None, dry_run: bool = False) -> 'CleanupConfig':
        """Create configuration for standalone cleanup script"""
        return cls(
            region=region or 'us-east-1',
            stack_name_prefix=stack_prefix or 'thingpress',
            dry_run=dry_run,
            cleanup_cloudformation_stacks=True,  # Full cleanup including stacks
            verification_wait_seconds=30,
            verbose=True,
        )


# Constants for resource identification
THINGPRESS_TAG_KEY = "created-by"
THINGPRESS_TAG_VALUE = "thingpress"
MANAGED_BY_TAG_KEY = "managed-by"
MANAGED_BY_TAG_VALUE = "thingpress"

# Default test patterns for IoT thing identification
DEFAULT_TEST_PATTERNS = [
    '0123',      # Microchip test certificate pattern
    'test_',     # Generic test prefix
    '_e2e',      # End-to-end test suffix
    'microchip_e2e',  # Specific E2E test pattern
]

# CloudFormation stack status filters
ACTIVE_STACK_STATUSES = [
    'CREATE_COMPLETE',
    'UPDATE_COMPLETE',
    'UPDATE_ROLLBACK_COMPLETE',
]

# S3 cleanup batch sizes
S3_DELETE_BATCH_SIZE = 1000
S3_LIST_MAX_KEYS = 1000

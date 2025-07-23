"""
Session manager for integration tests with automatic token refresh
"""

import boto3
import time
from datetime import datetime, timedelta
from botocore.exceptions import ClientError
import logging

logger = logging.getLogger(__name__)

class ExtendedSessionManager:
    """Manages AWS sessions with automatic refresh for long-running tests"""
    
    def __init__(self, duration_hours=2):
        """Initialize session manager
        
        Args:
            duration_hours: Desired session duration in hours
        """
        self.duration_hours = duration_hours
        self.session = None
        self.credentials = None
        self.expiration = None
        self.refresh_threshold_minutes = 10  # Refresh when 10 minutes left
        
        # Initialize session
        self._create_extended_session()
    
    def _create_extended_session(self):
        """Create a new extended session"""
        try:
            # Get current session to check identity
            current_session = boto3.Session()
            sts_client = current_session.client('sts')
            
            # Determine max duration based on identity type
            caller_identity = sts_client.get_caller_identity()
            arn = caller_identity.get('Arn', '')
            
            if ':assumed-role/' in arn:
                # Assumed roles are limited to 1 hour
                max_duration_seconds = 3600
                logger.warning("Using assumed role - limited to 1 hour sessions")
            else:
                # IAM users can have up to 12 hours
                max_duration_seconds = min(self.duration_hours * 3600, 12 * 3600)
                logger.info(f"Using IAM user - requesting {max_duration_seconds // 3600} hour session")
            
            # Get session token
            response = sts_client.get_session_token(
                DurationSeconds=max_duration_seconds
            )
            
            self.credentials = response['Credentials']
            self.expiration = self.credentials['Expiration']
            
            # Create new session with extended credentials
            self.session = boto3.Session(
                aws_access_key_id=self.credentials['AccessKeyId'],
                aws_secret_access_key=self.credentials['SecretAccessKey'],
                aws_session_token=self.credentials['SessionToken']
            )
            
            logger.info(f"Extended session created, expires: {self.expiration}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create extended session: {e}")
            # Fall back to default session
            self.session = boto3.Session()
            self.expiration = datetime.now() + timedelta(hours=1)
            return False
    
    def get_session(self):
        """Get current session, refreshing if necessary
        
        Returns:
            boto3.Session
        """
        if self._needs_refresh():
            logger.info("Session needs refresh, creating new session...")
            self._create_extended_session()
        
        return self.session
    
    def _needs_refresh(self):
        """Check if session needs refresh
        
        Returns:
            bool: True if session needs refresh
        """
        if not self.expiration:
            return True
        
        # Check if we're within the refresh threshold
        time_until_expiry = self.expiration - datetime.now()
        threshold = timedelta(minutes=self.refresh_threshold_minutes)
        
        return time_until_expiry < threshold
    
    def get_client(self, service_name, **kwargs):
        """Get AWS client with current session
        
        Args:
            service_name: AWS service name (e.g., 'iot', 's3')
            **kwargs: Additional arguments for client creation
            
        Returns:
            AWS client
        """
        session = self.get_session()
        return session.client(service_name, **kwargs)
    
    def get_resource(self, service_name, **kwargs):
        """Get AWS resource with current session
        
        Args:
            service_name: AWS service name (e.g., 'iot', 's3')
            **kwargs: Additional arguments for resource creation
            
        Returns:
            AWS resource
        """
        session = self.get_session()
        return session.resource(service_name, **kwargs)
    
    def time_until_expiry(self):
        """Get time until session expires
        
        Returns:
            timedelta or None if no expiration set
        """
        if not self.expiration:
            return None
        
        return self.expiration - datetime.now()
    
    def is_expired(self):
        """Check if session is expired
        
        Returns:
            bool: True if expired
        """
        if not self.expiration:
            return False
        
        return datetime.now() >= self.expiration

# Global session manager instance
_session_manager = None

def get_session_manager(duration_hours=2):
    """Get global session manager instance
    
    Args:
        duration_hours: Session duration in hours
        
    Returns:
        ExtendedSessionManager
    """
    global _session_manager
    
    if _session_manager is None:
        _session_manager = ExtendedSessionManager(duration_hours)
    
    return _session_manager

def get_extended_client(service_name, **kwargs):
    """Get AWS client with extended session
    
    Args:
        service_name: AWS service name
        **kwargs: Additional client arguments
        
    Returns:
        AWS client
    """
    manager = get_session_manager()
    return manager.get_client(service_name, **kwargs)

def get_extended_resource(service_name, **kwargs):
    """Get AWS resource with extended session
    
    Args:
        service_name: AWS service name
        **kwargs: Additional resource arguments
        
    Returns:
        AWS resource
    """
    manager = get_session_manager()
    return manager.get_resource(service_name, **kwargs)

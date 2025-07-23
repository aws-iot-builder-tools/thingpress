#!/usr/bin/env python3
"""
Configure AWS session with extended duration for integration testing
"""

import boto3
import os
from datetime import datetime, timedelta
import json

def get_extended_session_credentials(duration_hours=4):
    """Get AWS credentials with extended duration
    
    Args:
        duration_hours: Duration in hours (max 12 for IAM users, 1 for assumed roles)
    
    Returns:
        Dictionary with credentials or None if failed
    """
    try:
        # Try to get current session info
        sts_client = boto3.client('sts')
        caller_identity = sts_client.get_caller_identity()
        
        print(f"Current identity: {caller_identity.get('Arn', 'Unknown')}")
        
        # Check if we're using an assumed role
        if ':assumed-role/' in caller_identity.get('Arn', ''):
            print("⚠️  Currently using assumed role - limited to 1 hour sessions")
            max_duration = 3600  # 1 hour
        else:
            print("✅ Using IAM user - can request longer sessions")
            max_duration = duration_hours * 3600
        
        # Get session token with extended duration
        response = sts_client.get_session_token(
            DurationSeconds=min(max_duration, duration_hours * 3600)
        )
        
        credentials = response['Credentials']
        expiration = credentials['Expiration']
        
        print(f"✅ Extended session created")
        print(f"   Duration: {max_duration // 3600} hours")
        print(f"   Expires: {expiration}")
        
        return {
            'aws_access_key_id': credentials['AccessKeyId'],
            'aws_secret_access_key': credentials['SecretAccessKey'],
            'aws_session_token': credentials['SessionToken'],
            'expiration': expiration.isoformat()
        }
        
    except Exception as e:
        print(f"❌ Failed to get extended session: {e}")
        return None

def save_credentials_to_env_file(credentials, file_path='.env.extended'):
    """Save credentials to environment file
    
    Args:
        credentials: Credentials dictionary
        file_path: Path to save environment file
    """
    try:
        with open(file_path, 'w') as f:
            f.write(f"# Extended AWS session credentials\n")
            f.write(f"# Generated: {datetime.now().isoformat()}\n")
            f.write(f"# Expires: {credentials['expiration']}\n")
            f.write(f"export AWS_ACCESS_KEY_ID={credentials['aws_access_key_id']}\n")
            f.write(f"export AWS_SECRET_ACCESS_KEY={credentials['aws_secret_access_key']}\n")
            f.write(f"export AWS_SESSION_TOKEN={credentials['aws_session_token']}\n")
        
        print(f"✅ Credentials saved to {file_path}")
        print(f"   To use: source {file_path}")
        
    except Exception as e:
        print(f"❌ Failed to save credentials: {e}")

def create_boto3_session_with_extended_credentials():
    """Create a boto3 session with extended credentials
    
    Returns:
        boto3.Session or None if failed
    """
    credentials = get_extended_session_credentials()
    if not credentials:
        return None
    
    try:
        session = boto3.Session(
            aws_access_key_id=credentials['aws_access_key_id'],
            aws_secret_access_key=credentials['aws_secret_access_key'],
            aws_session_token=credentials['aws_session_token']
        )
        
        # Test the session
        sts = session.client('sts')
        identity = sts.get_caller_identity()
        print(f"✅ Extended session working: {identity.get('Arn', 'Unknown')}")
        
        return session
        
    except Exception as e:
        print(f"❌ Failed to create extended session: {e}")
        return None

def main():
    """Main function"""
    print("🔐 AWS Extended Session Configuration")
    print("=" * 60)
    
    # Get extended credentials
    credentials = get_extended_session_credentials(duration_hours=4)
    
    if credentials:
        # Save to environment file
        save_credentials_to_env_file(credentials)
        
        print("\n" + "=" * 60)
        print("🎯 Next Steps:")
        print("1. Source the credentials:")
        print("   source .env.extended")
        print("\n2. Run your integration tests:")
        print("   python test/integration/manual_integration_test.py")
        print("\n3. Or export directly:")
        print(f"   export AWS_ACCESS_KEY_ID={credentials['aws_access_key_id']}")
        print(f"   export AWS_SECRET_ACCESS_KEY={credentials['aws_secret_access_key']}")
        print(f"   export AWS_SESSION_TOKEN={credentials['aws_session_token']}")
        
    else:
        print("\n" + "=" * 60)
        print("❌ Failed to get extended credentials")
        print("💡 Alternative solutions:")
        print("1. Use AWS CLI profiles with assume-role")
        print("2. Use EC2 instance profiles")
        print("3. Use AWS SSO with longer session duration")

if __name__ == "__main__":
    main()

"""
Tagging utilities for integration tests
"""

import boto3
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)

def verify_thing_tags(thing_name: str, expected_tags: Dict[str, str] = None) -> Dict[str, Any]:
    """Verify that an IoT Thing has the expected tags
    
    Args:
        thing_name: Name of the IoT Thing
        expected_tags: Dictionary of expected tag key-value pairs
                      Defaults to {'created-by': 'thingpress', 'managed-by': 'thingpress'}
    
    Returns:
        Dictionary with verification results
    """
    if expected_tags is None:
        expected_tags = {'created-by': 'thingpress', 'managed-by': 'thingpress'}
    
    iot_client = boto3.client('iot')
    result = {
        'thing_name': thing_name,
        'exists': False,
        'tags_found': {},
        'expected_tags': expected_tags,
        'tags_match': False,
        'missing_tags': [],
        'extra_tags': {},
        'errors': []
    }
    
    try:
        # Get thing details
        thing_response = iot_client.describe_thing(thingName=thing_name)
        thing_arn = thing_response['thingArn']
        result['exists'] = True
        
        # Get tags
        tags_response = iot_client.list_tags_for_resource(resourceArn=thing_arn)
        tags = tags_response.get('tags', [])
        
        # Convert tags to dictionary
        tags_dict = {tag['Key']: tag['Value'] for tag in tags}
        result['tags_found'] = tags_dict
        
        # Check expected tags
        missing_tags = []
        for key, expected_value in expected_tags.items():
            if key not in tags_dict:
                missing_tags.append(key)
            elif tags_dict[key] != expected_value:
                missing_tags.append(f"{key} (expected: {expected_value}, found: {tags_dict[key]})")
        
        result['missing_tags'] = missing_tags
        result['tags_match'] = len(missing_tags) == 0
        
        # Find extra tags (not in expected)
        extra_tags = {k: v for k, v in tags_dict.items() if k not in expected_tags}
        result['extra_tags'] = extra_tags
        
        logger.info("Thing %s tag verification: %s", thing_name, 
                   "PASS" if result['tags_match'] else "FAIL")
        
    except Exception as e:
        error_msg = f"Failed to verify tags for thing {thing_name}: {str(e)}"
        result['errors'].append(error_msg)
        logger.error(error_msg)
    
    return result

def verify_certificate_tags(certificate_id: str, expected_tags: Dict[str, str] = None) -> Dict[str, Any]:
    """Verify that an IoT Certificate has the expected tags
    
    Args:
        certificate_id: ID of the IoT Certificate
        expected_tags: Dictionary of expected tag key-value pairs
                      Defaults to {'created-by': 'thingpress', 'managed-by': 'thingpress'}
    
    Returns:
        Dictionary with verification results
    """
    if expected_tags is None:
        expected_tags = {'created-by': 'thingpress', 'managed-by': 'thingpress'}
    
    iot_client = boto3.client('iot')
    result = {
        'certificate_id': certificate_id,
        'exists': False,
        'tags_found': {},
        'expected_tags': expected_tags,
        'tags_match': False,
        'missing_tags': [],
        'extra_tags': {},
        'errors': []
    }
    
    try:
        # Get certificate details
        cert_response = iot_client.describe_certificate(certificateId=certificate_id)
        cert_arn = cert_response['certificateDescription']['certificateArn']
        result['exists'] = True
        
        # Get tags
        tags_response = iot_client.list_tags_for_resource(resourceArn=cert_arn)
        tags = tags_response.get('tags', [])
        
        # Convert tags to dictionary
        tags_dict = {tag['Key']: tag['Value'] for tag in tags}
        result['tags_found'] = tags_dict
        
        # Check expected tags
        missing_tags = []
        for key, expected_value in expected_tags.items():
            if key not in tags_dict:
                missing_tags.append(key)
            elif tags_dict[key] != expected_value:
                missing_tags.append(f"{key} (expected: {expected_value}, found: {tags_dict[key]})")
        
        result['missing_tags'] = missing_tags
        result['tags_match'] = len(missing_tags) == 0
        
        # Find extra tags (not in expected)
        extra_tags = {k: v for k, v in tags_dict.items() if k not in expected_tags}
        result['extra_tags'] = extra_tags
        
        logger.info("Certificate %s tag verification: %s", certificate_id, 
                   "PASS" if result['tags_match'] else "FAIL")
        
    except Exception as e:
        error_msg = f"Failed to verify tags for certificate {certificate_id}: {str(e)}"
        result['errors'].append(error_msg)
        logger.error(error_msg)
    
    return result

def cleanup_test_objects(test_prefix: str = "test-", dry_run: bool = True) -> Dict[str, Any]:
    """Clean up test objects created during integration testing
    
    Args:
        test_prefix: Prefix to identify test objects
        dry_run: If True, only list objects without deleting
    
    Returns:
        Dictionary with cleanup results
    """
    iot_client = boto3.client('iot')
    result = {
        'test_things': [],
        'test_certificates': [],
        'deleted_things': [],
        'deleted_certificates': [],
        'errors': [],
        'dry_run': dry_run
    }
    
    try:
        # Find test things
        things_response = iot_client.list_things()
        for thing in things_response.get('things', []):
            thing_name = thing['thingName']
            if thing_name.startswith(test_prefix):
                result['test_things'].append(thing_name)
        
        # Find test certificates by checking thing principals
        for thing_name in result['test_things']:
            try:
                principals_response = iot_client.list_thing_principals(thingName=thing_name)
                for principal in principals_response.get('principals', []):
                    if 'cert/' in principal:
                        cert_id = principal.split('/')[-1]
                        if cert_id not in result['test_certificates']:
                            result['test_certificates'].append(cert_id)
            except Exception as e:
                logger.warning("Failed to get principals for thing %s: %s", thing_name, str(e))
        
        if dry_run:
            logger.info("DRY RUN: Found %d test things and %d test certificates", 
                       len(result['test_things']), len(result['test_certificates']))
            return result
        
        # Delete test things
        for thing_name in result['test_things']:
            try:
                # Detach principals first
                principals_response = iot_client.list_thing_principals(thingName=thing_name)
                for principal in principals_response.get('principals', []):
                    iot_client.detach_thing_principal(thingName=thing_name, principal=principal)
                
                # Delete thing
                iot_client.delete_thing(thingName=thing_name)
                result['deleted_things'].append(thing_name)
                logger.info("Deleted test thing: %s", thing_name)
                
            except Exception as e:
                error_msg = f"Failed to delete thing {thing_name}: {str(e)}"
                result['errors'].append(error_msg)
                logger.error(error_msg)
        
        # Delete test certificates
        for cert_id in result['test_certificates']:
            try:
                # Update to inactive first
                iot_client.update_certificate(certificateId=cert_id, newStatus='INACTIVE')
                
                # Delete certificate
                iot_client.delete_certificate(certificateId=cert_id)
                result['deleted_certificates'].append(cert_id)
                logger.info("Deleted test certificate: %s", cert_id)
                
            except Exception as e:
                error_msg = f"Failed to delete certificate {cert_id}: {str(e)}"
                result['errors'].append(error_msg)
                logger.error(error_msg)
    
    except Exception as e:
        error_msg = f"Cleanup operation failed: {str(e)}"
        result['errors'].append(error_msg)
        logger.error(error_msg)
    
    return result

def find_thingpress_objects_for_cleanup() -> Dict[str, Any]:
    """Find all Thingpress objects that can be cleaned up
    
    Returns:
        Dictionary with found objects
    """
    try:
        # Import here to avoid circular imports
        import sys
        from pathlib import Path
        project_root = Path(__file__).parent.parent.parent.parent
        sys.path.append(str(project_root / 'src/layer_utils'))
        
        from aws_utils import list_thingpress_things, list_thingpress_certificates
        
        things = list_thingpress_things()
        certificates = list_thingpress_certificates()
        
        return {
            'thingpress_things': things,
            'thingpress_certificates': certificates,
            'total_objects': len(things) + len(certificates)
        }
        
    except Exception as e:
        logger.error("Failed to find Thingpress objects: %s", str(e))
        return {
            'thingpress_things': [],
            'thingpress_certificates': [],
            'total_objects': 0,
            'error': str(e)
        }

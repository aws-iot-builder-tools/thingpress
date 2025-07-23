#!/usr/bin/env python3
"""
Test script for Thingpress IoT object tagging functionality
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))
sys.path.append(str(project_root / 'src'))

import boto3

def list_thingpress_things():
    """List all IoT Things created by Thingpress"""
    iot_client = boto3.client('iot')
    thingpress_things = []
    
    try:
        # List all things (paginated)
        paginator = iot_client.get_paginator('list_things')
        
        for page in paginator.paginate():
            for thing in page.get('things', []):
                thing_name = thing['thingName']
                thing_arn = thing['thingArn']
                
                try:
                    # Get tags for this thing
                    tags_response = iot_client.list_tags_for_resource(resourceArn=thing_arn)
                    tags = tags_response.get('tags', [])
                    
                    # Check if created by Thingpress
                    for tag in tags:
                        if tag.get('Key') == 'created-by' and tag.get('Value') == 'thingpress':
                            thingpress_things.append(thing_name)
                            break
                            
                except Exception as error:
                    print(f"Warning: Failed to get tags for thing {thing_name}: {error}")
                    continue
                    
    except Exception as error:
        print(f"Error: Failed to list things: {error}")
        raise error
    
    return thingpress_things

def list_thingpress_certificates():
    """List all IoT Certificates created by Thingpress"""
    iot_client = boto3.client('iot')
    thingpress_certificates = []
    
    try:
        # List all certificates (paginated)
        paginator = iot_client.get_paginator('list_certificates')
        
        for page in paginator.paginate():
            for cert in page.get('certificates', []):
                certificate_id = cert['certificateId']
                certificate_arn = cert['certificateArn']
                
                try:
                    # Get tags for this certificate
                    tags_response = iot_client.list_tags_for_resource(resourceArn=certificate_arn)
                    tags = tags_response.get('tags', [])
                    
                    # Check if created by Thingpress
                    for tag in tags:
                        if tag.get('Key') == 'created-by' and tag.get('Value') == 'thingpress':
                            thingpress_certificates.append(certificate_id)
                            break
                            
                except Exception as error:
                    print(f"Warning: Failed to get tags for certificate {certificate_id}: {error}")
                    continue
                    
    except Exception as error:
        print(f"Error: Failed to list certificates: {error}")
        raise error
    
    return thingpress_certificates

def test_list_thingpress_objects():
    """Test listing Thingpress-created objects"""
    print("🔍 Testing Thingpress Object Discovery")
    print("=" * 60)
    
    try:
        # List Thingpress things
        print("📋 Finding Thingpress Things...")
        thingpress_things = list_thingpress_things()
        print(f"   Found {len(thingpress_things)} things created by Thingpress:")
        for thing in thingpress_things[:10]:  # Show first 10
            print(f"     - {thing}")
        if len(thingpress_things) > 10:
            print(f"     ... and {len(thingpress_things) - 10} more")
        
        # List Thingpress certificates
        print("\n🔐 Finding Thingpress Certificates...")
        thingpress_certificates = list_thingpress_certificates()
        print(f"   Found {len(thingpress_certificates)} certificates created by Thingpress:")
        for cert in thingpress_certificates[:10]:  # Show first 10
            print(f"     - {cert}")
        if len(thingpress_certificates) > 10:
            print(f"     ... and {len(thingpress_certificates) - 10} more")
            
        return len(thingpress_things), len(thingpress_certificates)
        
    except Exception as e:
        print(f"❌ Error listing Thingpress objects: {e}")
        return 0, 0

def test_cleanup_dry_run():
    """Test cleanup in dry-run mode"""
    print("\n🧹 Testing Cleanup (Dry Run)")
    print("=" * 60)
    
    try:
        thingpress_things = list_thingpress_things()
        thingpress_certificates = list_thingpress_certificates()
        
        results = {
            'things_found': thingpress_things,
            'certificates_found': thingpress_certificates,
            'errors': []
        }
        
        print(f"📋 Dry Run Results:")
        print(f"   Things found: {len(results['things_found'])}")
        print(f"   Certificates found: {len(results['certificates_found'])}")
        
        return results
        
    except Exception as e:
        print(f"❌ Error in cleanup dry run: {e}")
        return None

def test_iot_permissions():
    """Test if we have the necessary IoT permissions"""
    print("\n🔐 Testing IoT Permissions")
    print("=" * 60)
    
    iot_client = boto3.client('iot')
    permissions = {
        'list_things': False,
        'list_certificates': False,
        'list_tags_for_resource': False
    }
    
    try:
        # Test list_things
        response = iot_client.list_things(maxResults=1)
        permissions['list_things'] = True
        print("   ✅ list_things: OK")
    except Exception as e:
        print(f"   ❌ list_things: {e}")
    
    try:
        # Test list_certificates
        response = iot_client.list_certificates(pageSize=1)
        permissions['list_certificates'] = True
        print("   ✅ list_certificates: OK")
    except Exception as e:
        print(f"   ❌ list_certificates: {e}")
    
    # Test tagging permissions with a sample ARN format
    try:
        # This will likely fail with access denied, but we can check the error type
        sample_arn = "arn:aws:iot:us-east-1:123456789012:thing/sample"
        iot_client.list_tags_for_resource(resourceArn=sample_arn)
    except iot_client.exceptions.ResourceNotFoundException:
        permissions['list_tags_for_resource'] = True
        print("   ✅ list_tags_for_resource: OK (resource not found is expected)")
    except Exception as e:
        if "AccessDenied" in str(e):
            print(f"   ❌ list_tags_for_resource: Access Denied")
        else:
            permissions['list_tags_for_resource'] = True
            print("   ✅ list_tags_for_resource: OK")
    
    return permissions

def main():
    """Main test function"""
    print("🏷️  Thingpress Tagging Test")
    print("=" * 60)
    print("This script tests the Thingpress IoT object tagging functionality")
    print("It will check for existing tagged objects and test permissions")
    print()
    
    # Test permissions first
    permissions = test_iot_permissions()
    
    if not all(permissions.values()):
        print("\n⚠️  Warning: Some IoT permissions are missing.")
        print("   The tagging functionality may not work properly.")
        print("   Required permissions:")
        print("   - iot:ListThings")
        print("   - iot:ListCertificates") 
        print("   - iot:ListTagsForResource")
        print("   - iot:TagResource (for creating tags)")
        return
    
    # Test object discovery
    thing_count, cert_count = test_list_thingpress_objects()
    
    # Test cleanup dry run
    cleanup_results = test_cleanup_dry_run()
    
    print("\n" + "=" * 60)
    print("🎯 Test Summary:")
    print(f"   Thingpress Things: {thing_count}")
    print(f"   Thingpress Certificates: {cert_count}")
    
    if cleanup_results:
        print(f"   Objects ready for cleanup: {len(cleanup_results['things_found']) + len(cleanup_results['certificates_found'])}")
    
    if thing_count > 0 or cert_count > 0:
        print("\n💡 Tagging appears to be working!")
        print("   Objects with 'created-by: thingpress' tags were found.")
    else:
        print("\n🤔 No tagged objects found.")
        print("   This could mean:")
        print("   - No objects have been created by Thingpress yet")
        print("   - Objects were created before tagging was implemented")
        print("   - There's an issue with the tagging implementation")
    
    print("\n🚀 Ready to test with real certificate processing!")

if __name__ == "__main__":
    main()

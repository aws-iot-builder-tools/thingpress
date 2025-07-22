#!/usr/bin/env python3
"""
Manual Integration Test Script

Simple script to manually test Thingpress providers by uploading manifests
and checking results. Based on yesterday's successful testing approach.
"""

import os
import sys
import json
import time
import boto3
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent.parent

def manual_integration_test():
    """Run manual integration test"""
    
    print("🧪 Manual Integration Test for Thingpress")
    print("=" * 60)
    print("This script will upload test manifests and help you verify results")
    print("=" * 60)
    
    # AWS clients
    s3_client = boto3.client('s3')
    iot_client = boto3.client('iot')
    cloudformation = boto3.client('cloudformation')
    
    # Get deployed resources
    print("\n📋 Getting deployed resources...")
    try:
        response = cloudformation.describe_stacks(StackName='sam-app')
        outputs = response['Stacks'][0]['Outputs']
        resources = {output['OutputKey']: output['OutputValue'] for output in outputs}
        print(f"   ✅ Found {len(resources)} resources")
    except Exception as e:
        print(f"   ❌ Failed to get resources: {e}")
        return False
    
    # Get current IoT thing count
    print("\n🔍 Getting baseline IoT thing count...")
    try:
        response = iot_client.list_things(maxResults=100)
        baseline_count = len(response.get('things', []))
        print(f"   📊 Current IoT things: {baseline_count}")
    except Exception as e:
        print(f"   ❌ Failed to get IoT things: {e}")
        return False
    
    # Test each provider
    providers = [
        {
            'name': 'Microchip',
            'bucket_key': 'MicrochipIngestPoint',
            'manifest': 'test/artifacts/ECC608C-TNGTLSU-B.json',
            'description': 'JSON manifest with Microchip certificates'
        },
        {
            'name': 'Espressif', 
            'bucket_key': 'EspressifIngestPoint',
            'manifest': 'test/artifacts/manifest-espressif.csv',
            'description': 'CSV manifest with Espressif certificates'
        },
        {
            'name': 'Infineon',
            'bucket_key': 'InfineonIngestPoint', 
            'manifest': 'test/artifacts/manifest-infineon.7z',
            'description': '7z archive with Infineon certificates'
        },
        {
            'name': 'Generated',
            'bucket_key': 'GeneratedIngestPoint',
            'manifest': 'test/artifacts/certificates_test.txt',
            'description': 'TXT file with generated certificates'
        }
    ]
    
    test_timestamp = int(time.time())
    uploaded_files = []
    
    print(f"\n🚀 Uploading test manifests (timestamp: {test_timestamp})...")
    
    for provider in providers:
        print(f"\n📤 Testing {provider['name']} Provider:")
        print(f"   Description: {provider['description']}")
        
        try:
            # Check if manifest exists
            manifest_path = project_root / provider['manifest']
            if not manifest_path.exists():
                print(f"   ❌ Manifest not found: {manifest_path}")
                continue
                
            # Get bucket
            bucket = resources.get(provider['bucket_key'])
            if not bucket:
                print(f"   ❌ Bucket not found for key: {provider['bucket_key']}")
                continue
                
            # Upload manifest
            file_extension = manifest_path.suffix
            key = f"manual-test/{test_timestamp}/{provider['name'].lower()}{file_extension}"
            
            with open(manifest_path, 'rb') as f:
                s3_client.upload_fileobj(f, bucket, key)
                
            uploaded_files.append((bucket, key))
            print(f"   ✅ Uploaded to s3://{bucket}/{key}")
            print(f"   📁 File size: {manifest_path.stat().st_size} bytes")
            
        except Exception as e:
            print(f"   ❌ Upload failed: {e}")
    
    if not uploaded_files:
        print("\n❌ No files were uploaded successfully")
        return False
    
    print(f"\n⏰ Waiting for processing...")
    print("   The system will now process the uploaded manifests.")
    print("   This typically takes 2-5 minutes depending on the provider.")
    print("   You can monitor progress in the AWS Console:")
    print("   - CloudWatch Logs for Lambda functions")
    print("   - IoT Core console for new things")
    print("   - SQS queues for message processing")
    
    # Wait and check periodically
    for wait_minutes in [2, 5, 8]:
        print(f"\n⏳ Waiting {wait_minutes} minutes for processing...")
        time.sleep(wait_minutes * 60)
        
        try:
            response = iot_client.list_things(maxResults=100)
            current_count = len(response.get('things', []))
            new_things = current_count - baseline_count
            
            print(f"   📊 Current IoT things: {current_count} (baseline: {baseline_count})")
            
            if new_things > 0:
                print(f"   🎉 SUCCESS: {new_things} new IoT things created!")
                
                # Show some recent things
                recent_things = response.get('things', [])[-new_things:]
                print(f"   📋 New things created:")
                for thing in recent_things[:5]:
                    print(f"      - {thing['thingName']}")
                if len(recent_things) > 5:
                    print(f"      ... and {len(recent_things) - 5} more")
                break
            else:
                print(f"   ⏳ No new things yet, continuing to wait...")
                
        except Exception as e:
            print(f"   ❌ Error checking IoT things: {e}")
    
    # Final status check
    print(f"\n🔍 Final Status Check:")
    try:
        response = iot_client.list_things(maxResults=100)
        final_count = len(response.get('things', []))
        total_new = final_count - baseline_count
        
        print(f"   📊 Final IoT thing count: {final_count}")
        print(f"   📈 New things created: {total_new}")
        
        if total_new > 0:
            print(f"   ✅ Integration test SUCCESSFUL!")
            print(f"   🎯 Thingpress processed manifests and created IoT things")
        else:
            print(f"   ⚠️  No new IoT things detected")
            print(f"   💡 This could mean:")
            print(f"      - Processing is still in progress (check CloudWatch logs)")
            print(f"      - Provider functions have issues (check Lambda logs)")
            print(f"      - Certificates were duplicates (idempotency working)")
            
    except Exception as e:
        print(f"   ❌ Error in final check: {e}")
    
    # Cleanup option
    print(f"\n🧹 Cleanup:")
    print(f"   Uploaded {len(uploaded_files)} test files")
    cleanup = input("   Delete uploaded test files? (y/N): ").lower().strip()
    
    if cleanup == 'y':
        for bucket, key in uploaded_files:
            try:
                s3_client.delete_object(Bucket=bucket, Key=key)
                print(f"   ✅ Deleted s3://{bucket}/{key}")
            except Exception as e:
                print(f"   ❌ Failed to delete s3://{bucket}/{key}: {e}")
    else:
        print("   📁 Test files left in S3 for inspection")
        for bucket, key in uploaded_files:
            print(f"      s3://{bucket}/{key}")
    
    print(f"\n" + "=" * 60)
    print(f"🎯 Manual Integration Test Complete!")
    print(f"   Check the results above to verify Thingpress functionality")
    print(f"=" * 60)
    
    return True

if __name__ == "__main__":
    success = manual_integration_test()
    exit(0 if success else 1)

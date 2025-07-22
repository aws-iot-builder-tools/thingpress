#!/usr/bin/env python3
"""
Debug Microchip Provider Test - Detailed logging to understand what's happening
"""

import os
import sys
import json
import boto3
import time
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.append(str(project_root))
sys.path.append(str(project_root / 'test/integration'))

from common.test_framework import ProviderComponentTest

def debug_microchip_provider():
    """Debug the Microchip provider to see what's happening"""
    
    print("🔍 DEBUG: Microchip Provider Component Test")
    print("=" * 60)
    
    # Initialize test
    test = ProviderComponentTest('microchip')
    
    # Get resources
    resources = test.get_deployed_resources()
    print(f"📋 Deployed Resources:")
    for key, value in resources.items():
        print(f"   {key}: {value}")
    
    # Upload test manifest
    manifest_path = project_root / 'test/artifacts/ECC608C-TNGTLSU-B.json'
    manifest_key = f"debug-test/{int(time.time())}/manifest.json"
    
    print(f"\n📤 Uploading test manifest:")
    print(f"   Source: {manifest_path}")
    print(f"   Bucket: {test.get_ingest_bucket()}")
    print(f"   Key: {manifest_key}")
    
    upload_success = test.upload_test_file(
        test.get_ingest_bucket(), 
        manifest_key, 
        str(manifest_path)
    )
    
    if not upload_success:
        print("❌ Failed to upload manifest")
        return
        
    print("✅ Manifest uploaded successfully")
    
    # Create provider event
    provider_event = test.create_test_manifest_event(test.get_ingest_bucket(), manifest_key)
    print(f"\n📨 Provider Event:")
    print(json.dumps(provider_event, indent=2))
    
    # Invoke provider function
    print(f"\n🚀 Invoking provider function: {test.get_provider_function_name()}")
    
    provider_response = test.invoke_lambda_function(
        test.get_provider_function_name(),
        provider_event
    )
    
    print(f"\n📥 Provider Response:")
    print(f"   Status Code: {provider_response['status_code']}")
    print(f"   Success: {provider_response['success']}")
    print(f"   Payload: {json.dumps(provider_response['payload'], indent=2)}")
    
    if provider_response['logs']:
        print(f"\n📜 Provider Logs:")
        print(provider_response['logs'])
    
    # Check all SQS queues for messages
    print(f"\n🔍 Checking all SQS queues for messages...")
    sqs = boto3.client('sqs')
    
    # List all queues
    queues_response = sqs.list_queues()
    all_queues = queues_response.get('QueueUrls', [])
    
    thingpress_queues = [q for q in all_queues if 'thingpress' in q.lower() or 'Thingpress' in q]
    
    print(f"   Found {len(thingpress_queues)} Thingpress queues:")
    
    for queue_url in thingpress_queues:
        queue_name = queue_url.split('/')[-1]
        
        # Get queue attributes
        try:
            attrs = sqs.get_queue_attributes(
                QueueUrl=queue_url,
                AttributeNames=['ApproximateNumberOfMessages', 'ApproximateNumberOfMessagesNotVisible']
            )
            
            visible_messages = int(attrs['Attributes'].get('ApproximateNumberOfMessages', 0))
            invisible_messages = int(attrs['Attributes'].get('ApproximateNumberOfMessagesNotVisible', 0))
            total_messages = visible_messages + invisible_messages
            
            print(f"   📊 {queue_name}: {total_messages} messages ({visible_messages} visible, {invisible_messages} in-flight)")
            
            # If there are messages, try to peek at one
            if visible_messages > 0:
                peek_response = sqs.receive_message(
                    QueueUrl=queue_url,
                    MaxNumberOfMessages=1,
                    WaitTimeSeconds=1
                )
                
                if 'Messages' in peek_response:
                    message = peek_response['Messages'][0]
                    print(f"      📄 Sample message body: {message['Body'][:200]}...")
                    
                    # Put the message back (don't delete it)
                    sqs.change_message_visibility(
                        QueueUrl=queue_url,
                        ReceiptHandle=message['ReceiptHandle'],
                        VisibilityTimeout=0
                    )
                    
        except Exception as e:
            print(f"   ❌ Error checking queue {queue_name}: {e}")
    
    # Cleanup
    print(f"\n🧹 Cleaning up test manifest...")
    try:
        test.s3_client.delete_object(Bucket=test.get_ingest_bucket(), Key=manifest_key)
        print("✅ Cleanup completed")
    except Exception as e:
        print(f"❌ Cleanup failed: {e}")
    
    print("\n" + "=" * 60)
    print("🔍 Debug test completed")

if __name__ == "__main__":
    debug_microchip_provider()

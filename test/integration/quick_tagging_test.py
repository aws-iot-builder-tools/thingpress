#!/usr/bin/env python3
"""
Quick tagging test that completes within token expiration limits
"""

import time
import boto3
import json
from datetime import datetime

def get_deployed_resources():
    """Get deployed CloudFormation resources"""
    cf_client = boto3.client('cloudformation')
    try:
        response = cf_client.describe_stacks(StackName='sam-app')
        outputs = response['Stacks'][0].get('Outputs', [])
        return {output['OutputKey']: output['OutputValue'] for output in outputs}
    except Exception as e:
        print(f"Warning: Could not get stack outputs: {e}")
        return {'MicrochipIngestPoint': 'thingpress-microchip-sam-app'}

def quick_tagging_test():
    """Quick test to verify tagging functionality"""
    print("🏷️  Quick Thingpress Tagging Test")
    print("=" * 60)
    print("This test uploads a manifest and checks for tagged objects")
    print("Designed to complete within AWS token expiration limits")
    print()
    
    try:
        # Get baseline
        print("📋 Getting baseline...")
        resources = get_deployed_resources()
        print(f"   Found {len(resources)} deployed resources")
        
        # Get current IoT object counts
        iot_client = boto3.client('iot')
        
        # Upload a test manifest to trigger processing
        print("\n📤 Uploading test manifest...")
        timestamp = int(time.time())
        test_key = f"quick-tagging-test/{timestamp}/manifest.json"
        
        # Use the actual test manifest format
        test_manifest = {
            "certificates": [
                {
                    "serialNumber": f"test-{timestamp}",
                    "certificate": "-----BEGIN CERTIFICATE-----\nMIIBkTCB+wIJAKtest...\n-----END CERTIFICATE-----"
                }
            ]
        }
        
        bucket_name = resources.get('MicrochipIngestPoint', 'thingpress-microchip-sam-app')
        
        # Upload manifest
        s3_client = boto3.client('s3')
        s3_client.put_object(
            Bucket=bucket_name,
            Key=test_key,
            Body=json.dumps(test_manifest),
            ContentType='application/json'
        )
        print(f"   ✅ Uploaded to s3://{bucket_name}/{test_key}")
        
        # Wait briefly for processing
        print("\n⏳ Waiting 45 seconds for processing...")
        time.sleep(45)
        
        # Check for tagged objects
        print("\n🔍 Checking for tagged objects...")
        
        # Check things with Thingpress tags
        thingpress_things = []
        try:
            things_response = iot_client.list_things(maxResults=100)
            for thing in things_response.get('things', []):
                thing_name = thing['thingName']
                thing_arn = thing['thingArn']
                
                try:
                    tags_response = iot_client.list_tags_for_resource(resourceArn=thing_arn)
                    tags = {tag['Key']: tag['Value'] for tag in tags_response.get('tags', [])}
                    
                    if tags.get('created-by') == 'thingpress':
                        thingpress_things.append({
                            'name': thing_name,
                            'tags': tags,
                            'created': thing.get('thingCreationDate', 'Unknown')
                        })
                
                except Exception as e:
                    continue  # Skip things we can't check
        
        except Exception as e:
            print(f"   ⚠️  Could not list things: {e}")
        
        # Check certificates with Thingpress tags
        thingpress_certs = []
        try:
            certs_response = iot_client.list_certificates(pageSize=100)
            for cert in certs_response.get('certificates', []):
                cert_id = cert['certificateId']
                cert_arn = cert['certificateArn']
                
                try:
                    tags_response = iot_client.list_tags_for_resource(resourceArn=cert_arn)
                    tags = {tag['Key']: tag['Value'] for tag in tags_response.get('tags', [])}
                    
                    if tags.get('created-by') == 'thingpress':
                        thingpress_certs.append({
                            'id': cert_id,
                            'tags': tags,
                            'created': cert.get('creationDate', 'Unknown')
                        })
                
                except Exception as e:
                    continue  # Skip certs we can't check
        
        except Exception as e:
            print(f"   ⚠️  Could not list certificates: {e}")
        
        # Display results
        if thingpress_things:
            print(f"\n✅ Found {len(thingpress_things)} Thingpress-tagged things:")
            for thing in thingpress_things[:5]:  # Show first 5
                print(f"   - {thing['name']} (created: {thing['created']})")
                print(f"     Tags: {thing['tags']}")
        
        if thingpress_certs:
            print(f"\n✅ Found {len(thingpress_certs)} Thingpress-tagged certificates:")
            for cert in thingpress_certs[:5]:  # Show first 5
                print(f"   - {cert['id']} (created: {cert['created']})")
                print(f"     Tags: {cert['tags']}")
        
        # Cleanup
        print("\n🧹 Cleaning up test manifest...")
        try:
            s3_client.delete_object(Bucket=bucket_name, Key=test_key)
            print("   ✅ Test manifest deleted")
        except Exception as e:
            print(f"   ⚠️  Could not delete test manifest: {e}")
        
        # Results
        print("\n" + "=" * 60)
        print("🎯 Quick Tagging Test Results:")
        print(f"   Tagged Things Found: {len(thingpress_things)}")
        print(f"   Tagged Certificates Found: {len(thingpress_certs)}")
        
        if len(thingpress_things) > 0 or len(thingpress_certs) > 0:
            print("\n🎉 SUCCESS: Tagging is working!")
            print("   Objects are being created with 'created-by: thingpress' tags")
            print("   Integration test cleanup can now identify Thingpress objects")
        else:
            print("\n🤔 No tagged objects found.")
            print("   This could indicate:")
            print("   - Processing hasn't completed yet (layer dependency issue)")
            print("   - Manifest format incorrect for this test")
            print("   - Tagging implementation needs debugging")
            print("\n💡 Try checking CloudWatch logs for processing errors:")
            print("   - /aws/lambda/sam-app-ThingpressMicrochipProviderFunction-*")
            print("   - /aws/lambda/sam-app-ThingpressBulkImporterFunction-*")
        
        return len(thingpress_things) + len(thingpress_certs) > 0
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = quick_tagging_test()
    exit(0 if success else 1)

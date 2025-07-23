#!/usr/bin/env python3
"""
Test circuit breaker behavior by directly invoking Lambda functions
"""

import boto3
import json
import time
from datetime import datetime

def invoke_function_and_check_logs(function_name, test_payload):
    """Invoke a Lambda function and immediately check its logs"""
    lambda_client = boto3.client('lambda')
    logs_client = boto3.client('logs')
    
    print(f"🚀 Invoking {function_name}...")
    
    try:
        # Invoke the function
        response = lambda_client.invoke(
            FunctionName=function_name,
            InvocationType='RequestResponse',
            Payload=json.dumps(test_payload)
        )
        
        # Get response
        status_code = response['StatusCode']
        payload = response['Payload'].read().decode()
        
        print(f"   Status: {status_code}")
        print(f"   Response: {payload[:200]}...")
        
        # Check for function errors
        if 'FunctionError' in response:
            print(f"   ❌ Function Error: {response['FunctionError']}")
        
        # Wait a moment for logs to appear
        time.sleep(2)
        
        # Get recent logs
        log_group_name = f"/aws/lambda/{function_name}"
        end_time = int(time.time() * 1000)
        start_time = int((time.time() - 300) * 1000)  # Last 5 minutes
        
        try:
            events_response = logs_client.filter_log_events(
                logGroupName=log_group_name,
                startTime=start_time,
                endTime=end_time,
                limit=50
            )
            
            recent_logs = events_response.get('events', [])
            print(f"   📋 Found {len(recent_logs)} recent log events")
            
            # Look for circuit breaker related logs
            circuit_logs = []
            error_logs = []
            
            for event in recent_logs:
                message = event['message']
                if 'circuit' in message.lower() or '🔥' in message or '🚨' in message:
                    circuit_logs.append(message)
                elif 'error' in message.lower() or 'exception' in message.lower():
                    error_logs.append(message)
            
            if circuit_logs:
                print(f"   🔥 Circuit Breaker Activity:")
                for log in circuit_logs[-3:]:  # Last 3
                    print(f"      {log.strip()}")
            
            if error_logs:
                print(f"   ❌ Error Activity:")
                for log in error_logs[-3:]:  # Last 3
                    print(f"      {log.strip()}")
            
            if not circuit_logs and not error_logs:
                print(f"   ℹ️  No circuit breaker or error activity detected")
                # Show last few logs for context
                for event in recent_logs[-3:]:
                    timestamp = datetime.fromtimestamp(event['timestamp'] / 1000)
                    print(f"      {timestamp}: {event['message'].strip()}")
        
        except Exception as e:
            print(f"   ⚠️  Could not retrieve logs: {e}")
        
        return status_code == 200
        
    except Exception as e:
        print(f"   ❌ Invocation failed: {e}")
        return False

def test_microchip_provider():
    """Test the Microchip provider function"""
    print("🧪 Testing Microchip Provider Function")
    print("=" * 50)
    
    # Create a test S3 event payload
    test_payload = {
        "Records": [
            {
                "eventVersion": "2.1",
                "eventSource": "aws:s3",
                "eventName": "ObjectCreated:Put",
                "s3": {
                    "bucket": {
                        "name": "thingpress-microchip-sam-app"
                    },
                    "object": {
                        "key": "test-circuit-breaker/manifest.json"
                    }
                }
            }
        ]
    }
    
    # Get the actual function name
    lambda_client = boto3.client('lambda')
    functions = lambda_client.list_functions()
    
    microchip_function = None
    for func in functions['Functions']:
        if 'ThingpressMicrochipProvider' in func['FunctionName']:
            microchip_function = func['FunctionName']
            break
    
    if microchip_function:
        return invoke_function_and_check_logs(microchip_function, test_payload)
    else:
        print("❌ Microchip provider function not found")
        return False

def test_bulk_importer():
    """Test the Bulk Importer function"""
    print("\n🧪 Testing Bulk Importer Function")
    print("=" * 50)
    
    # Create a test SQS event payload
    test_payload = {
        "Records": [
            {
                "eventSource": "aws:sqs",
                "body": json.dumps({
                    "thing": "test-circuit-breaker-thing",
                    "certificate": "-----BEGIN CERTIFICATE-----\ntest\n-----END CERTIFICATE-----",
                    "policy_name": "test-policy"
                })
            }
        ]
    }
    
    # Get the actual function name
    lambda_client = boto3.client('lambda')
    functions = lambda_client.list_functions()
    
    bulk_function = None
    for func in functions['Functions']:
        if 'ThingpressBulkImporter' in func['FunctionName']:
            bulk_function = func['FunctionName']
            break
    
    if bulk_function:
        return invoke_function_and_check_logs(bulk_function, test_payload)
    else:
        print("❌ Bulk importer function not found")
        return False

def main():
    """Main test function"""
    print("🔍 Circuit Breaker Behavior Test")
    print("=" * 60)
    print("This test directly invokes Lambda functions to observe circuit breaker behavior")
    print()
    
    # Test both key functions
    microchip_success = test_microchip_provider()
    bulk_success = test_bulk_importer()
    
    print("\n" + "=" * 60)
    print("🎯 Test Results:")
    print(f"   Microchip Provider: {'✅ Success' if microchip_success else '❌ Failed'}")
    print(f"   Bulk Importer: {'✅ Success' if bulk_success else '❌ Failed'}")
    
    if not microchip_success and not bulk_success:
        print("\n💡 Both functions failed - this suggests:")
        print("   1. Layer dependency issue (functions can't import modules)")
        print("   2. Circuit breakers may be opening immediately")
        print("   3. Functions may be timing out before circuit logic runs")
    elif microchip_success and not bulk_success:
        print("\n💡 Provider works but Bulk Importer fails - this suggests:")
        print("   1. Issue is in the bulk import processing logic")
        print("   2. Circuit breakers may be protecting downstream services")
    else:
        print("\n💡 Functions are working - issue may be elsewhere")
    
    print("\n🔧 Next Steps:")
    print("1. Check the logs above for circuit breaker activity")
    print("2. If no circuit activity, the issue is likely import/layer related")
    print("3. If circuit activity found, investigate which operations are failing")

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Circuit Breaker Diagnostics for Thingpress
"""

import sys
import os
from pathlib import Path
import boto3
import json
import time
from datetime import datetime, timedelta

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))
sys.path.append(str(project_root / 'src'))

def get_cloudwatch_logs_for_circuit_breaker():
    """Get recent CloudWatch logs that mention circuit breaker activity"""
    logs_client = boto3.client('logs')
    
    # Get log groups for Lambda functions
    log_groups = [
        '/aws/lambda/sam-app-ThingpressMicrochipProviderFunction',
        '/aws/lambda/sam-app-ThingpressBulkImporterFunction',
        '/aws/lambda/sam-app-ThingpressInfineonProviderFunction',
        '/aws/lambda/sam-app-ThingpressEspressifProviderFunction',
        '/aws/lambda/sam-app-ThingpressGeneratedProviderFunction'
    ]
    
    # Look for circuit breaker related logs in the last hour
    end_time = int(time.time() * 1000)
    start_time = int((time.time() - 3600) * 1000)  # 1 hour ago
    
    circuit_breaker_events = []
    
    for log_group_prefix in log_groups:
        try:
            # Find actual log group names (they have suffixes)
            response = logs_client.describe_log_groups(
                logGroupNamePrefix=log_group_prefix
            )
            
            for log_group in response.get('logGroups', []):
                log_group_name = log_group['logGroupName']
                print(f"🔍 Checking {log_group_name}...")
                
                try:
                    # Search for circuit breaker related messages
                    events_response = logs_client.filter_log_events(
                        logGroupName=log_group_name,
                        startTime=start_time,
                        endTime=end_time,
                        filterPattern='circuit'
                    )
                    
                    for event in events_response.get('events', []):
                        circuit_breaker_events.append({
                            'timestamp': datetime.fromtimestamp(event['timestamp'] / 1000),
                            'log_group': log_group_name,
                            'message': event['message']
                        })
                        
                except Exception as e:
                    print(f"   ⚠️  Could not read logs from {log_group_name}: {e}")
                    
        except Exception as e:
            print(f"   ⚠️  Could not find log group {log_group_prefix}: {e}")
    
    return circuit_breaker_events

def get_lambda_function_errors():
    """Get recent Lambda function errors that might trigger circuit breakers"""
    logs_client = boto3.client('logs')
    
    # Look for errors in the last hour
    end_time = int(time.time() * 1000)
    start_time = int((time.time() - 3600) * 1000)
    
    error_patterns = [
        'ERROR',
        'Exception',
        'ModuleNotFoundError',
        'ImportError',
        'aws_utils',
        'Traceback'
    ]
    
    all_errors = []
    
    log_groups = [
        '/aws/lambda/sam-app-ThingpressMicrochipProviderFunction',
        '/aws/lambda/sam-app-ThingpressBulkImporterFunction'
    ]
    
    for log_group_prefix in log_groups:
        try:
            response = logs_client.describe_log_groups(
                logGroupNamePrefix=log_group_prefix
            )
            
            for log_group in response.get('logGroups', []):
                log_group_name = log_group['logGroupName']
                
                for pattern in error_patterns:
                    try:
                        events_response = logs_client.filter_log_events(
                            logGroupName=log_group_name,
                            startTime=start_time,
                            endTime=end_time,
                            filterPattern=pattern
                        )
                        
                        for event in events_response.get('events', []):
                            all_errors.append({
                                'timestamp': datetime.fromtimestamp(event['timestamp'] / 1000),
                                'log_group': log_group_name,
                                'pattern': pattern,
                                'message': event['message']
                            })
                            
                    except Exception as e:
                        continue
                        
        except Exception as e:
            continue
    
    return all_errors

def test_circuit_breaker_operations():
    """Test individual operations that use circuit breakers"""
    print("🔧 Testing Circuit Breaker Operations")
    print("=" * 60)
    
    # Import here to avoid import issues
    try:
        sys.path.append(str(project_root / 'src/layer_utils'))
        from aws_utils import (
            s3_object_bytes, send_sqs_message, verify_queue,
            get_thing_type_arn, get_policy_arn, process_thing_group
        )
        from circuit_state import _circuit_states, clear_circuits
        
        print("✅ Successfully imported circuit breaker functions")
        
        # Clear any existing circuit state
        clear_circuits()
        print("🔄 Cleared existing circuit states")
        
        # Test S3 operation (should work)
        print("\n📤 Testing S3 operation...")
        try:
            # Try to download a small object from a known bucket
            bucket_name = 'thingpress-microchip-sam-app'
            test_result = s3_object_bytes(bucket_name, 'nonexistent-key')
            print("   ⚠️  Unexpected success - object should not exist")
        except Exception as e:
            if 'NoSuchKey' in str(e):
                print("   ✅ S3 operation working (expected NoSuchKey error)")
            else:
                print(f"   ❌ S3 operation failed: {e}")
        
        # Test SQS operation
        print("\n📨 Testing SQS operation...")
        try:
            queue_url = 'https://sqs.us-east-1.amazonaws.com/517295686160/nonexistent-queue'
            result = verify_queue(queue_url)
            print(f"   ⚠️  Unexpected result: {result}")
        except Exception as e:
            if 'NonExistentQueue' in str(e) or 'QueueDoesNotExist' in str(e):
                print("   ✅ SQS operation working (expected queue not found)")
            else:
                print(f"   ❌ SQS operation failed: {e}")
        
        # Check circuit states
        print(f"\n🔍 Current circuit states: {len(_circuit_states)} circuits")
        for operation, state in _circuit_states.items():
            print(f"   - {operation}: open={state.is_open}, failures={state.failure_count}")
        
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("   This suggests the layer dependency issue is real!")
        return False
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

def analyze_recent_invocations():
    """Analyze recent Lambda invocations for patterns"""
    lambda_client = boto3.client('lambda')
    
    functions = [
        'sam-app-ThingpressMicrochipProviderFunction',
        'sam-app-ThingpressBulkImporterFunction'
    ]
    
    print("📊 Analyzing Recent Lambda Invocations")
    print("=" * 60)
    
    for function_prefix in functions:
        try:
            # Get actual function name
            response = lambda_client.list_functions()
            actual_function = None
            
            for func in response.get('Functions', []):
                if func['FunctionName'].startswith(function_prefix):
                    actual_function = func['FunctionName']
                    break
            
            if actual_function:
                print(f"\n🔍 Function: {actual_function}")
                
                # Get function configuration
                config = lambda_client.get_function(FunctionName=actual_function)
                print(f"   Runtime: {config['Configuration']['Runtime']}")
                print(f"   Timeout: {config['Configuration']['Timeout']}s")
                print(f"   Memory: {config['Configuration']['MemorySize']}MB")
                
                # Check layers
                layers = config['Configuration'].get('Layers', [])
                print(f"   Layers: {len(layers)}")
                for layer in layers:
                    print(f"     - {layer['Arn']}")
                
            else:
                print(f"   ⚠️  Function not found: {function_prefix}")
                
        except Exception as e:
            print(f"   ❌ Error analyzing {function_prefix}: {e}")

def main():
    """Main diagnostic function"""
    print("🔍 Thingpress Circuit Breaker Diagnostics")
    print("=" * 60)
    print("Investigating potential circuit breaker issues...")
    print()
    
    # Test circuit breaker operations
    operations_working = test_circuit_breaker_operations()
    
    # Analyze Lambda functions
    analyze_recent_invocations()
    
    # Get circuit breaker logs
    print("\n📋 Recent Circuit Breaker Activity")
    print("=" * 60)
    circuit_events = get_cloudwatch_logs_for_circuit_breaker()
    
    if circuit_events:
        print(f"Found {len(circuit_events)} circuit breaker events:")
        for event in circuit_events[-10:]:  # Show last 10
            print(f"   {event['timestamp']}: {event['message'].strip()}")
    else:
        print("No recent circuit breaker activity found")
    
    # Get error logs
    print("\n❌ Recent Error Activity")
    print("=" * 60)
    error_events = get_lambda_function_errors()
    
    if error_events:
        print(f"Found {len(error_events)} error events:")
        # Group by error type
        error_types = {}
        for event in error_events:
            pattern = event['pattern']
            if pattern not in error_types:
                error_types[pattern] = []
            error_types[pattern].append(event)
        
        for error_type, events in error_types.items():
            print(f"\n   {error_type} ({len(events)} occurrences):")
            for event in events[-3:]:  # Show last 3 of each type
                print(f"     {event['timestamp']}: {event['message'].strip()[:100]}...")
    else:
        print("No recent error activity found")
    
    # Summary
    print("\n" + "=" * 60)
    print("🎯 Diagnostic Summary:")
    
    if not operations_working:
        print("❌ ISSUE: Cannot import circuit breaker functions")
        print("   This confirms a layer dependency problem!")
        print("   Recommendation: Investigate layer deployment and attachment")
    else:
        print("✅ Circuit breaker functions can be imported")
        print("   Issue may be in specific operation failures")
    
    if circuit_events:
        print(f"⚠️  Found {len(circuit_events)} circuit breaker events")
        print("   Circuits may be opening due to repeated failures")
    else:
        print("ℹ️  No circuit breaker activity detected")
    
    if error_events:
        print(f"❌ Found {len(error_events)} error events")
        print("   These errors may be triggering circuit breakers")
    else:
        print("✅ No recent errors detected")
    
    print("\n💡 Next Steps:")
    if not operations_working:
        print("1. Investigate layer deployment: aws lambda get-layer-version")
        print("2. Check function layer attachment")
        print("3. Verify layer contains aws_utils module")
    else:
        print("1. Enable X-Ray tracing for detailed performance analysis")
        print("2. Add more detailed circuit breaker logging")
        print("3. Monitor specific operation failures")

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Enable AWS X-Ray tracing for Thingpress Lambda functions to diagnose performance issues
"""

import boto3
import json

def enable_xray_for_functions():
    """Enable X-Ray tracing for all Thingpress Lambda functions"""
    lambda_client = boto3.client('lambda')
    
    # Get all Thingpress functions
    functions = []
    response = lambda_client.list_functions()
    
    for func in response.get('Functions', []):
        if 'sam-app-Thingpress' in func['FunctionName']:
            functions.append(func['FunctionName'])
    
    print(f"🔍 Found {len(functions)} Thingpress functions")
    
    for function_name in functions:
        try:
            print(f"\n📊 Enabling X-Ray for {function_name}...")
            
            # Update function configuration to enable X-Ray
            response = lambda_client.update_function_configuration(
                FunctionName=function_name,
                TracingConfig={
                    'Mode': 'Active'
                }
            )
            
            print(f"   ✅ X-Ray enabled - Tracing Mode: {response['TracingConfig']['Mode']}")
            
        except Exception as e:
            print(f"   ❌ Failed to enable X-Ray: {e}")
    
    return functions

def check_xray_status():
    """Check current X-Ray tracing status"""
    lambda_client = boto3.client('lambda')
    
    response = lambda_client.list_functions()
    
    print("📊 Current X-Ray Tracing Status:")
    print("=" * 60)
    
    for func in response.get('Functions', []):
        if 'sam-app-Thingpress' in func['FunctionName']:
            tracing_mode = func.get('TracingConfig', {}).get('Mode', 'PassThrough')
            status = "✅ Active" if tracing_mode == 'Active' else "❌ Disabled"
            print(f"   {func['FunctionName']}: {status}")

def get_recent_traces():
    """Get recent X-Ray traces for analysis"""
    xray_client = boto3.client('xray')
    
    from datetime import datetime, timedelta
    import time
    
    # Get traces from the last hour
    end_time = datetime.now()
    start_time = end_time - timedelta(hours=1)
    
    try:
        response = xray_client.get_trace_summaries(
            TimeRangeType='TimeRangeByStartTime',
            StartTime=start_time,
            EndTime=end_time,
            FilterExpression='service("sam-app-Thingpress*")'
        )
        
        traces = response.get('TraceSummaries', [])
        print(f"\n🔍 Found {len(traces)} recent traces")
        
        for trace in traces[:5]:  # Show first 5
            print(f"\n📊 Trace ID: {trace['Id']}")
            print(f"   Duration: {trace.get('Duration', 0):.3f}s")
            print(f"   Response Time: {trace.get('ResponseTime', 0):.3f}s")
            
            if trace.get('HasError'):
                print(f"   ❌ Has Errors: {trace.get('ErrorRootCauses', [])}")
            
            if trace.get('HasFault'):
                print(f"   🚨 Has Faults: {trace.get('FaultRootCauses', [])}")
            
            # Get detailed trace
            try:
                detail_response = xray_client.batch_get_traces(
                    TraceIds=[trace['Id']]
                )
                
                for trace_detail in detail_response.get('Traces', []):
                    for segment in trace_detail.get('Segments', []):
                        segment_doc = json.loads(segment['Document'])
                        print(f"   📋 Service: {segment_doc.get('name', 'Unknown')}")
                        
                        # Look for subsegments (AWS service calls)
                        for subsegment in segment_doc.get('subsegments', []):
                            if subsegment.get('error') or subsegment.get('fault'):
                                print(f"      ❌ {subsegment.get('name', 'Unknown')}: {subsegment.get('cause', {}).get('exceptions', [])}")
                            
            except Exception as e:
                print(f"   ⚠️  Could not get trace details: {e}")
        
        return traces
        
    except Exception as e:
        print(f"❌ Failed to get X-Ray traces: {e}")
        return []

def main():
    """Main function"""
    print("📊 AWS X-Ray Tracing Setup for Thingpress")
    print("=" * 60)
    
    # Check current status
    check_xray_status()
    
    # Enable X-Ray tracing
    print(f"\n🔧 Enabling X-Ray Tracing...")
    functions = enable_xray_for_functions()
    
    # Check status again
    print(f"\n📊 Updated X-Ray Status:")
    check_xray_status()
    
    print(f"\n💡 Next Steps:")
    print("1. Trigger some certificate processing:")
    print("   python test/integration/manual_integration_test.py")
    print("\n2. Wait 2-3 minutes for traces to appear")
    print("\n3. Check traces:")
    print("   python scripts/debug/enable_xray_tracing.py --check-traces")
    print("\n4. View in AWS Console:")
    print("   https://console.aws.amazon.com/xray/home#/traces")
    
    # If --check-traces argument provided, get recent traces
    import sys
    if '--check-traces' in sys.argv:
        print(f"\n🔍 Recent X-Ray Traces:")
        print("=" * 60)
        get_recent_traces()

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Test Lambda import directly
"""

import boto3
import json

def test_lambda_import():
    """Test the Lambda function import directly"""
    
    lambda_client = boto3.client('lambda')
    
    # Simple test event
    test_event = {
        "test": "import_check"
    }
    
    # Invoke the function
    try:
        response = lambda_client.invoke(
            FunctionName='sam-app-ThingpressMicrochipProviderFunction-YQ9VEQyIbh3H',
            InvocationType='RequestResponse',
            Payload=json.dumps(test_event)
        )
        
        payload = json.loads(response['Payload'].read())
        print("Lambda Response:")
        print(json.dumps(payload, indent=2))
        
        if 'errorMessage' in payload:
            print(f"\nError: {payload['errorMessage']}")
            print(f"Error Type: {payload.get('errorType', 'Unknown')}")
            
        return 'errorMessage' not in payload
        
    except Exception as e:
        print(f"Failed to invoke Lambda: {e}")
        return False

if __name__ == "__main__":
    success = test_lambda_import()
    print(f"\nImport test: {'✅ PASSED' if success else '❌ FAILED'}")

#!/usr/bin/env python3
import os
import sys
import argparse
import subprocess
import json
import time
import boto3
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('integration-tests')

def parse_args():
    parser = argparse.ArgumentParser(description='Run Thingpress integration tests')
    parser.add_argument('--provider', choices=['all', 'espressif', 'infineon', 'microchip', 'generated'],
                        default='all', help='Provider to test (default: all)')
    parser.add_argument('--region', default='us-east-1', help='AWS region (default: us-east-1)')
    parser.add_argument('--profile', help='AWS profile to use')
    parser.add_argument('--test-id', help='Test ID to use (default: auto-generated)')
    parser.add_argument('--no-cleanup', action='store_true', help='Skip stack cleanup after tests')
    return parser.parse_args()

def run_test_for_provider(provider, region, profile, test_id):
    """Deploy and run tests for a specific provider."""
    logger.info(f"Running integration tests for {provider} provider")
    
    # Set up environment
    env = os.environ.copy()
    if profile:
        env['AWS_PROFILE'] = profile
    env['AWS_REGION'] = region
    
    # Directory for this provider's tests
    provider_dir = os.path.join(os.path.dirname(__file__), f"../test/integration/{provider}")
    
    if not os.path.exists(provider_dir):
        logger.error(f"Test directory not found for provider: {provider}")
        return False
    
    # Generate a test ID if not provided
    if not test_id:
        test_id = f"test-{int(time.time())}"
    
    # Deploy the test stack
    logger.info(f"Deploying test stack for {provider} with test ID: {test_id}")
    deploy_cmd = [
        "sam", "deploy",
        "--stack-name", f"thingpress-{provider}-test-{test_id}",
        "--parameter-overrides", f"TestId={test_id}",
        "--no-confirm-changeset",
        "--capabilities", "CAPABILITY_IAM"
    ]
    
    try:
        # Change to provider directory
        os.chdir(provider_dir)
        
        # Deploy the stack
        deploy_result = subprocess.run(deploy_cmd, env=env, check=True, capture_output=True, text=True)
        logger.info(f"Stack deployment successful for {provider}")
        
        # Get the deployed Lambda function name
        cloudformation = boto3.client('cloudformation', region_name=region)
        stack_outputs = cloudformation.describe_stacks(
            StackName=f"thingpress-{provider}-test-{test_id}"
        )['Stacks'][0]['Outputs']
        
        lambda_function_name = next(
            (output['OutputValue'] for output in stack_outputs if output['OutputKey'] == 'TestFunctionName'),
            None
        )
        
        if not lambda_function_name:
            logger.error(f"Could not find Lambda function name in stack outputs for {provider}")
            return False
        
        # Invoke the Lambda function to run the test
        logger.info(f"Invoking test Lambda function: {lambda_function_name}")
        lambda_client = boto3.client('lambda', region_name=region)
        response = lambda_client.invoke(
            FunctionName=lambda_function_name,
            InvocationType='RequestResponse',
            LogType='Tail'
        )
        
        # Check the response
        status_code = response['StatusCode']
        if status_code != 200:
            logger.error(f"Lambda invocation failed with status code: {status_code}")
            return False
        
        # Parse the response payload
        payload = json.loads(response['Payload'].read().decode('utf-8'))
        logger.info(f"Raw payload: {payload}")
        
        # Handle both direct payload and API Gateway response format
        if 'body' in payload:
            # API Gateway response format
            body = json.loads(payload['body']) if isinstance(payload['body'], str) else payload['body']
            success = body.get('success', False)
            error = body.get('error', 'Unknown error')
            duration = body.get('duration', 0)
            logger.info(f"Parsed body: {body}")
        else:
            # Direct payload format
            success = payload.get('success', False)
            error = payload.get('error', 'Unknown error')
            duration = payload.get('duration', 0)
            logger.info(f"Direct payload format")
            
        if not success:
            logger.error(f"Test failed for {provider}: {error}")
            return False
        
        logger.info(f"Test successful for {provider} (duration: {duration:.2f}ms)")
        return True
        
    except subprocess.CalledProcessError as e:
        logger.error(f"Error deploying stack for {provider}: {e}")
        logger.error(f"STDOUT: {e.stdout}")
        logger.error(f"STDERR: {e.stderr}")
        return False
    except Exception as e:
        logger.error(f"Error running test for {provider}: {e}")
        return False

def cleanup_test_stack(provider, test_id, region, profile):
    """Clean up the test stack."""
    logger.info(f"Cleaning up test stack for {provider}")
    
    # Set up environment
    env = os.environ.copy()
    if profile:
        env['AWS_PROFILE'] = profile
    env['AWS_REGION'] = region
    
    # Directory for this provider's tests
    provider_dir = os.path.join(os.path.dirname(__file__), f"../test/integration/{provider}")
    
    # Delete the stack
    delete_cmd = [
        "sam", "delete",
        "--stack-name", f"thingpress-{provider}-test-{test_id}",
        "--no-prompts"
    ]
    
    try:
        # Change to provider directory
        os.chdir(provider_dir)
        
        # Delete the stack
        delete_result = subprocess.run(delete_cmd, env=env, check=True, capture_output=True, text=True)
        logger.info(f"Stack deletion successful for {provider}")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Error deleting stack for {provider}: {e}")
        logger.error(f"STDOUT: {e.stdout}")
        logger.error(f"STDERR: {e.stderr}")
        return False
    except Exception as e:
        logger.error(f"Error during cleanup for {provider}: {e}")
        return False

def main():
    args = parse_args()
    
    # Determine which providers to test
    providers = ['espressif', 'infineon', 'microchip', 'generated'] if args.provider == 'all' else [args.provider]
    
    # Generate a test ID if not provided
    test_id = args.test_id or f"run-{int(time.time())}"
    
    # Track results
    results = {}
    start_time = datetime.now()
    
    # Run tests for each provider
    for provider in providers:
        provider_start_time = datetime.now()
        success = run_test_for_provider(provider, args.region, args.profile, f"{test_id}-{provider}")
        provider_end_time = datetime.now()
        duration_ms = (provider_end_time - provider_start_time).total_seconds() * 1000
        
        results[provider] = {
            'success': success,
            'duration_ms': duration_ms
        }
        
        # Clean up if requested and test failed
        if not args.no_cleanup:
            cleanup_test_stack(provider, f"{test_id}-{provider}", args.region, args.profile)
    
    # Print summary
    end_time = datetime.now()
    total_duration_ms = (end_time - start_time).total_seconds() * 1000
    
    logger.info("\n=== Test Results Summary ===")
    logger.info(f"Total Duration: {total_duration_ms:.2f}ms")
    
    all_success = True
    for provider, result in results.items():
        status = "PASSED" if result['success'] else "FAILED"
        logger.info(f"{provider}: {status} ({result['duration_ms']:.2f}ms)")
        if not result['success']:
            all_success = False
    
    # Exit with appropriate status code
    sys.exit(0 if all_success else 1)

if __name__ == "__main__":
    main()

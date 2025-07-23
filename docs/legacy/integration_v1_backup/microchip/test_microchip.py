import os
import json
import boto3
import logging
import time
import sys
import traceback
from datetime import datetime

# Add project root to Python path to import from src
sys.path.append(os.path.join(os.path.dirname(__file__), '../../..'))

# Import test utilities with fallback for Lambda environment
try:
    from test.integration.common.test_utils import TestMetrics, ResourceCleanup
except ImportError:
    # Fallback for Lambda environment - copy the classes locally or use simplified versions
    class TestMetrics:
        def __init__(self, test_name):
            self.test_name = test_name
            self.metrics = {"test_name": test_name, "success": False}
        def save_metrics(self, bucket):
            pass  # Simplified for Lambda
    
    class ResourceCleanup:
        def __init__(self):
            pass
        def add_s3_object(self, bucket, key):
            pass
        def cleanup(self):
            pass

# Import the provider handler - adjust import path as needed
try:
    from src.provider_microchip.provider_microchip.main import lambda_handler as provider_handler
    from src.bulk_importer.main import lambda_handler as importer_handler
except ImportError:
    # Fallback for when running in Lambda
    sys.path.append('/var/task')
    from provider_microchip.main import lambda_handler as provider_handler
    from main import lambda_handler as importer_handler

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def setup_test_environment():
    """Set up the test environment with required resources."""
    test_id = os.environ.get('TEST_ID', f"test-{int(time.time())}")
    input_bucket = os.environ.get('INPUT_BUCKET')
    output_bucket = os.environ.get('OUTPUT_BUCKET')
    input_queue = os.environ.get('INPUT_QUEUE')
    output_queue = os.environ.get('OUTPUT_QUEUE')
    
    # Upload test manifest to S3
    s3 = boto3.client('s3')
    manifest_path = os.path.join(os.path.dirname(__file__), '../../artifacts/ECC608C-TNGTLSU-B.json')
    manifest_key = f"test-manifests/microchip-{test_id}.json"
    
    with open(manifest_path, 'rb') as f:
        s3.upload_fileobj(f, input_bucket, manifest_key)
    
    return {
        'test_id': test_id,
        'input_bucket': input_bucket,
        'output_bucket': output_bucket,
        'input_queue': input_queue,
        'output_queue': output_queue,
        'manifest_key': manifest_key
    }

def run_microchip_test(env):
    """Run the Microchip provider test."""
    metrics = TestMetrics("microchip_integration_test")
    cleanup = ResourceCleanup()
    
    # Add the manifest to cleanup
    cleanup.add_s3_object(env['input_bucket'], env['manifest_key'])
    
    try:
        # Step 1: Trigger the Microchip provider
        metrics.start_step("trigger_provider")
        provider_event = {
            'Records': [{
                'body': json.dumps({
                    'bucket': env['input_bucket'],
                    'key': env['manifest_key']
                })
            }]
        }
        
        provider_context = type('obj', (object,), {
            'function_name': 'test_microchip_provider',
            'aws_request_id': f"req-{env['test_id']}"
        })
        
        provider_response = provider_handler(provider_event, provider_context)
        metrics.end_step(True)
        
        # Step 2: Wait for messages in the output queue
        metrics.start_step("check_output_queue")
        sqs = boto3.client('sqs')
        queue_url = sqs.get_queue_url(QueueName=env['output_queue'])['QueueUrl']
        
        # Poll for messages with timeout
        start_time = time.time()
        timeout = 60  # seconds
        messages = []
        
        while time.time() - start_time < timeout:
            response = sqs.receive_message(
                QueueUrl=queue_url,
                MaxNumberOfMessages=10,
                WaitTimeSeconds=5
            )
            
            if 'Messages' in response:
                messages.extend(response['Messages'])
                
                # Delete received messages
                for message in response['Messages']:
                    sqs.delete_message(
                        QueueUrl=queue_url,
                        ReceiptHandle=message['ReceiptHandle']
                    )
                
                # If we have at least one message, we can proceed
                if len(messages) > 0:
                    break
        
        if not messages:
            raise Exception("No messages received in output queue within timeout")
        
        metrics.end_step(True)
        
        # Step 3: Process a sample message with the bulk importer
        metrics.start_step("process_bulk_importer")
        
        # Create a test IoT policy for the test
        iot = boto3.client('iot')
        policy_name = f"TestPolicy-{env['test_id']}"
        policy_document = json.dumps({
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Action": "iot:Connect",
                "Resource": "*"
            }]
        })
        
        iot.create_policy(
            policyName=policy_name,
            policyDocument=policy_document
        )
        
        # Sample message from the queue
        sample_message = json.loads(messages[0]['Body'])
        
        # Add certificate ID to cleanup list if available
        if 'certificateId' in sample_message:
            cleanup.add_iot_certificate(sample_message['certificateId'])
        
        # Add thing name to cleanup list if available
        if 'thing' in sample_message:
            cleanup.add_iot_thing(sample_message['thing'])
        
        # Create bulk importer event
        importer_event = {
            'Records': [{
                'body': messages[0]['Body']
            }]
        }
        
        # Set environment variables for bulk importer
        os.environ['IOT_POLICY'] = policy_name
        os.environ['IOT_THING_TYPE'] = f"TestThingType-{env['test_id']}"
        os.environ['IOT_THING_GROUP'] = f"TestThingGroup-{env['test_id']}"
        
        # Create thing type and group
        try:
            iot.create_thing_type(thingTypeName=os.environ['IOT_THING_TYPE'])
        except Exception as e:
            logger.warning(f"Error creating thing type: {e}")
            
        try:
            iot.create_thing_group(thingGroupName=os.environ['IOT_THING_GROUP'])
        except Exception as e:
            logger.warning(f"Error creating thing group: {e}")
        
        importer_context = type('obj', (object,), {
            'function_name': 'test_bulk_importer',
            'aws_request_id': f"req-importer-{env['test_id']}"
        })
        
        importer_response = importer_handler(importer_event, importer_context)
        metrics.end_step(True)
        
        # Step 4: Verify the thing was created
        metrics.start_step("verify_thing_creation")
        thing_name = sample_message['thing']
        
        thing_response = iot.describe_thing(thingName=thing_name)
        if thing_response['thingName'] != thing_name:
            raise Exception(f"Thing name mismatch: {thing_response['thingName']} != {thing_name}")
            
        metrics.end_step(True)
        
        # Test successful
        return metrics.end_test(True)
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        logger.error(traceback.format_exc())
        metrics.end_test(False, error=str(e))
        return metrics.metrics
    finally:
        # Clean up resources
        try:
            # Delete IoT policy
            if 'policy_name' in locals():
                iot = boto3.client('iot')
                iot.delete_policy(policyName=policy_name)
                
            # Delete thing type
            if os.environ.get('IOT_THING_TYPE'):
                try:
                    iot.delete_thing_type(thingTypeName=os.environ['IOT_THING_TYPE'])
                except Exception as e:
                    logger.warning(f"Error deleting thing type: {e}")
                    
            # Delete thing group
            if os.environ.get('IOT_THING_GROUP'):
                try:
                    iot.delete_thing_group(thingGroupName=os.environ['IOT_THING_GROUP'])
                except Exception as e:
                    logger.warning(f"Error deleting thing group: {e}")
            
            # Run resource cleanup
            cleanup.cleanup()
            
        except Exception as cleanup_error:
            logger.error(f"Error during cleanup: {cleanup_error}")

def lambda_handler(event, context):
    """Lambda handler for the integration test."""
    try:
        # Set up test environment
        env = setup_test_environment()
        
        # Run the test
        test_results = run_microchip_test(env)
        
        # Save metrics to S3
        metrics = TestMetrics("microchip_integration_test")
        metrics.metrics = test_results
        metrics.save_metrics(env['output_bucket'])
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'success': test_results['success'],
                'testId': env['test_id'],
                'duration': test_results['duration_ms']
            })
        }
        
    except Exception as e:
        logger.error(f"Test execution failed: {e}")
        logger.error(traceback.format_exc())
        return {
            'statusCode': 500,
            'body': json.dumps({
                'success': False,
                'error': str(e)
            })
        }

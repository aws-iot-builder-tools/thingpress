"""
Component Integration Test Framework
Tests deployed Thingpress components through their interfaces
"""

import os
import time
import logging
import json
import base64
from datetime import datetime
import boto3
from botocore.exceptions import ClientError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

class ComponentTestFramework:
    """Base framework for testing deployed Thingpress components"""

    def __init__(self, test_name: str, region: str = 'us-east-1'):
        self.test_name = test_name
        self.region = region
        self.test_id = f"{test_name}-{int(time.time())}"
        self.logger = logging.getLogger(f"test.{test_name}")

        # Test resources to cleanup
        self.cleanup_resources = []

        # Test results
        self.results = {
            'test_name': test_name,
            'test_id': self.test_id,
            'start_time': datetime.now().isoformat(),
            'steps': [],
            'success': False,
            'error': None
        }

    def log_step(self, step_name: str, description: str = ""):
        """Log a test step"""
        step = {
            'name': step_name,
            'description': description,
            'start_time': datetime.now().isoformat(),
            'success': False,
            'duration_ms': 0,
            'details': {}
        }
        self.results['steps'].append(step)
        self.logger.info("🔄 Starting step: %s - %s", step_name, description)
        return step

    def complete_step(self, step: dict, success: bool = True, details: dict | None = None):
        """Complete a test step"""
        end_time = datetime.now()
        start_time = datetime.fromisoformat(step['start_time'])
        duration_ms = (end_time - start_time).total_seconds() * 1000

        step['success'] = success
        step['duration_ms'] = duration_ms
        step['end_time'] = end_time.isoformat()
        if details:
            step['details'].update(details)

        status = "✅" if success else "❌"
        self.logger.info(
            "%s Completed step: %s (%d:.2fms)",
            status, step['name'], duration_ms
        )

    def get_deployed_resources(self, stack_name: str = None) -> dict[str, str]:
        """Get deployed Thingpress resources from CloudFormation stack"""
        cloudformation = boto3.client('cloudformation', region_name=self.region)

        # Try multiple possible stack names
        if stack_name:
            stack_names = [stack_name]
        else:
            # Check environment variable first
            env_stack = os.environ.get('THINGPRESS_STACK_NAME')
            if env_stack:
                stack_names = [env_stack]
            else:
                stack_names = [
                    'sam-app',  # Default SAM stack name
                    'thingpress',  # Common custom name
                ]

                # Also try to find stacks with 'thingpress' in the name
                try:
                    list_response = cloudformation.list_stacks(
                        StackStatusFilter=['CREATE_COMPLETE', 'UPDATE_COMPLETE']
                    )
                    for stack in list_response.get('StackSummaries', []):
                        if 'thingpress' in stack['StackName'].lower():
                            stack_names.append(stack['StackName'])
                except Exception:
                    pass

        # Try each stack name
        last_error = None
        for name in stack_names:
            try:
                response = cloudformation.describe_stacks(StackName=name)
                outputs = response['Stacks'][0]['Outputs']

                resources = {}
                for output in outputs:
                    key = output['OutputKey']
                    value = output['OutputValue']
                    resources[key] = value

                self.logger.info(
                    "Found %d deployed resources from stack: %s",
                    len(resources), name
                )
                return resources

            except Exception as e:
                last_error = e
                continue

        # If we get here, none of the stack names worked
        self.logger.error(
            "Failed to get deployed resources. Tried stacks: %s",
            stack_names
        )
        self.logger.error("Last error: %s", last_error)
        raise Exception(
            f"Could not find Thingpress stack. "
            f"Tried: {stack_names}. Last error: {last_error}"
        )

    def invoke_lambda_function(self, function_name: str, payload: dict) -> dict:
        """Invoke a Lambda function and return the response"""
        try:
            lambda_client = boto3.client('lambda', region_name=self.region)
            response = lambda_client.invoke(
                FunctionName=function_name,
                InvocationType='RequestResponse',
                LogType='Tail',
                Payload=json.dumps(payload)
            )

            # Parse response
            status_code = response['StatusCode']
            payload_response = json.loads(response['Payload'].read().decode('utf-8'))

            # Get logs if available
            logs = ""
            if 'LogResult' in response:
                logs = base64.b64decode(response['LogResult']).decode('utf-8')

            return {
                'status_code': status_code,
                'payload': payload_response,
                'logs': logs,
                'success': status_code == 200
            }

        except Exception as e:
            self.logger.error("Failed to invoke Lambda %s: %s", function_name, e)
            raise

    def upload_test_file(self, bucket: str, key: str, file_path: str) -> bool:
        """Upload a test file to S3"""
        s3_client = boto3.client('s3', region_name=self.region)
        try:
            with open(file_path, 'rb') as f:
                s3_client.upload_fileobj(f, bucket, key)
            self.logger.info("Uploaded test file to s3://%s/%s", bucket, key)
            return True

        except ClientError as e:
            self.logger.error("Failed to upload test file: %s", e)
            return False

    def wait_for_sqs_messages(self, queue_url: str, timeout_seconds: int = 60,
                             expected_count: int = 1) -> list[dict]:
        """Wait for messages to appear in SQS queue"""
        messages = []
        start_time = time.time()
        sqs_client = boto3.client('sqs', region_name=self.region)

        while time.time() - start_time < timeout_seconds and len(messages) < expected_count:
            response = sqs_client.receive_message(
                QueueUrl=queue_url,
                MaxNumberOfMessages=10,
                WaitTimeSeconds=5
            )

            if 'Messages' in response:
                new_messages = response['Messages']
                messages.extend(new_messages)

                # Delete received messages to avoid reprocessing
                for message in new_messages:
                    sqs_client.delete_message(
                        QueueUrl=queue_url,
                        ReceiptHandle=message['ReceiptHandle']
                    )

            time.sleep(1)

        self.logger.info(
            "Received %s messages from queue in %d:.2fs",
            len(messages), time.time() - start_time
        )
        return messages

    def check_iot_thing_exists(self, thing_name: str) -> bool:
        """Check if an IoT thing exists"""
        iot_client = boto3.client('iot', region_name=self.region)

        try:
            iot_client.describe_thing(thingName=thing_name)
            return True
        except iot_client.exceptions.ResourceNotFoundException:
            return False
        except ClientError as e:
            self.logger.error("Error checking IoT thing %s: %s", thing_name, e)
            return False

    def cleanup_test_resources(self):
        """Clean up test resources"""
        self.logger.info("🧹 Starting test resource cleanup")
        iot_client = boto3.client('iot', region_name=self.region)

        for resource_type, *args in self.cleanup_resources:
            thing_name = args[0]

            # retrieve list of principals for this thing
            # TODO: this is a paginated operation and as such requires pagination loop
            try:
                principals_raw = iot_client.list_thing_principals_v2(thingName=thing_name)
                principals = principals_raw.get('principals', [])
                # To ease use later on, parse out the certificateId.
            except ClientError as e:
                self.logger.warning("Failed to cleanup %s %s: %s", resource_type, args, e)

            try:
                for principal in principals:
                    # detach any policies attached to the principal
                    attached_policies = iot_client.list_principal_policies(principal=principal)
                    for policy in attached_policies.get('policies', []):
                        iot_client.detach_policy(
                            policyName=policy['policyName'],
                            target=principal
                        )
            except ClientError as e:
                self.logger.warning("Failed to cleanup %s %s: %s", resource_type, args, e)

            try:
                for principal in principals:
                    principal_id = principal.split('/').pop()
                    iot_client.update_certificate(certificateId=principal_id,
                                                  newStatus='INACTIVE')
                    iot_client.delete_certificate(certificateId=principal_id,
                                                  forceDelete=True)
            except ClientError as e:
                self.logger.warning("Failed to cleanup %s %s: %s", resource_type, args, e)

            iot_client.delete_thing(thingName=thing_name)
            self.logger.info("Deleted IoT thing: %s", thing_name)

    def finalize_test(self, success: bool = True, error: str | None = None):
        """Finalize test results"""
        self.results['end_time'] = datetime.now().isoformat()
        self.results['success'] = success
        if error:
            self.results['error'] = error

        # Calculate total duration
        start_time = datetime.fromisoformat(self.results['start_time'])
        end_time = datetime.fromisoformat(self.results['end_time'])
        total_duration = (end_time - start_time).total_seconds() * 1000
        self.results['total_duration_ms'] = total_duration

        # Cleanup resources
        self.cleanup_test_resources()

        # Log final result
        status = "🎉 PASSED" if success else "❌ FAILED"
        self.logger.info("%s Test %s completed in %d:.2fms",
                         status, self.test_name, total_duration)

        if error:
            self.logger.error("Error: %s", error)

        return self.results

class ProviderComponentTest(ComponentTestFramework):
    """Base class for testing provider components"""

    def __init__(self, provider_name: str, region: str = 'us-east-1'):
        super().__init__(f"{provider_name}_provider_component", region)
        self.provider_name = provider_name
        self.resources = self.get_deployed_resources()

    def get_provider_function_name(self) -> str:
        """Get the deployed provider function name"""
        key = f"{self.provider_name.title()}ProviderFunction"
        if key not in self.resources:
            raise ValueError(f"Provider function not found for {self.provider_name}")
        return self.resources[key]

    def get_ingest_bucket(self) -> str:
        """Get the provider's ingest S3 bucket"""
        key = f"{self.provider_name.title()}IngestPoint"
        if key not in self.resources:
            raise ValueError(f"Ingest bucket not found for {self.provider_name}")
        return self.resources[key]

    def get_bulk_importer_function(self) -> str:
        """Get the bulk importer function name"""
        return self.resources['BulkImporterFunction']

    def create_test_manifest_event(
            self, bucket: str, key: str,
            additional_config: dict = None) -> dict:
        """Create test event for provider with optional config"""
        event = {
            'Records': [{
                'eventSource': 'aws:sqs',
                'eventName': 'aws:sqs:SendMessage',
                'body': json.dumps({
                    'bucket': bucket,
                    'key': key
                })
            }]
        }

        # Add additional config to the body if provided
        if additional_config:
            body = json.loads(event['Records'][0]['body'])
            body.update(additional_config)
            event['Records'][0]['body'] = json.dumps(body)

        return event

    def get_queue_url(self, queue_name_key: str) -> str:
        """Get SQS queue URL from resources"""
        if queue_name_key in self.resources:
            queue_name = self.resources[queue_name_key]
        else:
            # Fallback: try to construct queue name
            queue_name = queue_name_key

        sqs_client = boto3.client('sqs', region_name=self.region)
        try:
            response = sqs_client.get_queue_url(QueueName=queue_name)
            return response['QueueUrl']
        except ClientError as e:
            self.logger.error(
                "Failed to get queue URL for %s: %s", queue_name, e
            )
            raise

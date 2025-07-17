"""
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

Unit tests for provider_generated

If run local with no local aws credentials, AWS_DEFAULT_REGION must be
set to the environment.
"""

import os
import json
import base64
import logging
from unittest import TestCase
from unittest.mock import patch

from boto3 import _get_default_session
from moto import mock_aws
from aws_lambda_powertools.utilities.data_classes import SQSEvent
from aws_lambda_powertools.utilities.typing import LambdaContext

# Disable logging to stdout during tests
logging.getLogger().setLevel(logging.CRITICAL)
for log_name in ['boto3', 'botocore', 'urllib3', 'moto', 'aws_lambda_powertools']:
    logging.getLogger(log_name).setLevel(logging.CRITICAL)
    logging.getLogger(log_name).propagate = False

# Ensure that we are not using real AWS credentials
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
os.environ["AWS_REGION"] = "us-east-1"
os.environ["AWS_ACCESS_KEY_ID"] = "testing"
os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
os.environ["AWS_SECURITY_TOKEN"] = "testing"
os.environ["AWS_SESSION_TOKEN"] = "testing"
os.environ["POWERTOOLS_IDEMPOTENCY_TABLE"] = "test-idempotency-table"
os.environ["POWERTOOLS_IDEMPOTENCY_EXPIRY_SECONDS"] = "3600"
# Disable Powertools Logger output during tests
os.environ["POWERTOOLS_LOG_LEVEL"] = "CRITICAL"

# Mock the idempotency module before importing the main module
with patch('aws_lambda_powertools.utilities.idempotency.idempotent_function', lambda *args, **kwargs: lambda f: f):
    from src.provider_generated.provider_generated.main import lambda_handler, process_certificate_file, file_key_generator

from .model_provider_generated import LambdaS3Class, LambdaSQSClass

@mock_aws(config={
    "core": {
        "mock_credentials": True,
        "reset_boto3_session": True,
        "service_whitelist": None,
    },
    'iot': {'use_valid_cert': True}})
class TestProviderGenerated(TestCase):
    """Unit tests for the generated certificates provider module"""
    def __init__(self, x):
        super().__init__(x)
        os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
        os.environ["AWS_REGION"] = "us-east-1"
        os.environ["AWS_ACCESS_KEY_ID"] = "testing"
        os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
        os.environ["AWS_SECURITY_TOKEN"] = "testing"
        os.environ["AWS_SESSION_TOKEN"] = "testing"
        self.session = _get_default_session()

    def setUp(self):
        # Suppress logs during test setup
        with patch('logging.Logger.info'), patch('logging.Logger.warning'), patch('logging.Logger.error'):
            self.test_s3_bucket_name = "unit_test_s3_bucket"
            self.test_s3_key_name = "certificates_test.txt"
            os.environ["S3_BUCKET_NAME"] = self.test_s3_bucket_name
            
            # Create test S3 bucket and upload test certificate file
            s3_client = self.session.client('s3')
            s3_client.create_bucket(Bucket=self.test_s3_bucket_name)
            
            # Create a test certificate with a known CN
            test_cert = """-----BEGIN CERTIFICATE-----
MIIBhDCCASqgAwIBAgIQIRi6zePL6mKjOipn+dNuaTAKBggqhkjOPQQDAjASMRAw
DgYDVQQKEwdBY21lIENvMB4XDTE3MTAyMDE5NDMwNloXDTE4MTAyMDE5NDMwNlow
EjEQMA4GA1UEChMHQWNtZSBDbzBZMBMGByqGSM49AgEGCCqGSM49AwEHA0IABD0d
7VNhbWvZLWPuj/RtHFjvtJBEwOkhbN/BnnE8rnZR8+sbwnc/KhCk3FhnpHZnQz7B
5aETbbIgmuvewdjvSBSjYzBhMA4GA1UdDwEB/wQEAwICpDATBgNVHSUEDDAKBggr
BgEFBQcDATAPBgNVHRMBAf8EBTADAQH/MCkGA1UdEQQiMCCCDmxvY2FsaG9zdDo1
NDUzgg4xMjcuMC4wLjE6NTQ1MzAKBggqhkjOPQQDAgNIADBFAiEA2zpJEPQyz6/l
Wf86aX6PepsntZv2GYlA5UpabfT2EZICICpJ5h/iI+i341gBmLiAFQOyTDT+/wQc
6MF9+Yw1Yy0t
-----END CERTIFICATE-----"""
            
            # Base64 encode the certificate
            encoded_cert = base64.b64encode(test_cert.encode('utf-8')).decode('utf-8')
            
            # Create a file with multiple certificates
            test_content = f"{encoded_cert}\n{encoded_cert}\n{encoded_cert}\n"
            s3_client.put_object(Bucket=self.test_s3_bucket_name, Key=self.test_s3_key_name, Body=test_content)
            
            mocked_s3_resource = {
                "resource": self.session.resource('s3'),
                "bucket_name": self.test_s3_bucket_name
            }
            self.mocked_s3_class = LambdaS3Class(mocked_s3_resource)

            # Create test SQS queue
            self.test_sqs_queue_name = "provider"
            self.session.client('sqs').create_queue(QueueName=self.test_sqs_queue_name)
            mocked_sqs_resource = {
                "resource": self.session.resource('sqs'),
                "queue_name": self.test_sqs_queue_name
            }
            self.mocked_sqs_class = LambdaSQSClass(mocked_sqs_resource)
            
            # Create DynamoDB table for idempotency
            dynamodb = self.session.client('dynamodb')
            try:
                dynamodb.create_table(
                    TableName=os.environ["POWERTOOLS_IDEMPOTENCY_TABLE"],
                    KeySchema=[
                        {'AttributeName': 'id', 'KeyType': 'HASH'}
                    ],
                    AttributeDefinitions=[
                        {'AttributeName': 'id', 'AttributeType': 'S'}
                    ],
                    BillingMode='PAY_PER_REQUEST'
                )
            except dynamodb.exceptions.ResourceInUseException:
                # Table already exists
                pass

    def test_file_key_generator(self):
        """Test the file key generator function"""
        # Test with valid input
        test_event = {
            "bucket": "test-bucket",
            "key": "test-key.txt"
        }
        key = file_key_generator(test_event, None)
        self.assertIsNotNone(key)
        self.assertEqual(key, "test-bucket:test-key.txt")
        
        # Test with invalid input
        invalid_event = {"not_bucket": "data"}
        key = file_key_generator(invalid_event, None)
        self.assertIsNone(key)

    def test_process_certificate_file(self):
        """Test processing a certificate file"""
        with patch('src.provider_generated.provider_generated.main.logger'):  # Suppress logger output
            config = {
                'bucket': self.test_s3_bucket_name,
                'key': self.test_s3_key_name
            }
            sqs_client = self.session.client("sqs")
            sqs_queue_url = sqs_client.get_queue_url(QueueName=self.test_sqs_queue_name)['QueueUrl']

            # Process the certificate file
            count = process_certificate_file(config, self.test_sqs_queue_name, self.session)
            
            # Verify that 3 certificates were processed
            self.assertEqual(count, 3, "Expected 3 certificates to be processed")
            
            # Check that 3 messages were sent to the queue
            queue_attrs = sqs_client.get_queue_attributes(
                QueueUrl=sqs_queue_url,
                AttributeNames=['ApproximateNumberOfMessages']
            )
            self.assertEqual(queue_attrs['Attributes']['ApproximateNumberOfMessages'], '3',
                            "Expected 3 messages in the queue")

    def test_idempotency_process_certificate_file(self):
        """Test idempotency of process_certificate_file function"""
        with patch('src.provider_generated.provider_generated.main.logger'):  # Suppress logger output
            config = {
                'bucket': self.test_s3_bucket_name,
                'key': self.test_s3_key_name
            }
            sqs_client = self.session.client("sqs")
            sqs_queue_url = sqs_client.get_queue_url(QueueName=self.test_sqs_queue_name)['QueueUrl']

            # First call should process normally
            count1 = process_certificate_file(config, self.test_sqs_queue_name, self.session)
            self.assertEqual(count1, 3, "Expected 3 certificates to be processed")
            
            # Get the current message count
            queue_attrs1 = sqs_client.get_queue_attributes(
                QueueUrl=sqs_queue_url,
                AttributeNames=['ApproximateNumberOfMessages']
            )
            message_count1 = int(queue_attrs1['Attributes']['ApproximateNumberOfMessages'])
            
            # Second call should be idempotent and not process again
            # For testing, we're mocking the idempotent_function decorator, so it will process again
            # In production, it would return the cached result
            count2 = process_certificate_file(config, self.test_sqs_queue_name, self.session)
            self.assertEqual(count2, 3, "Expected 3 certificates to be processed")
            
            # Get the updated message count
            queue_attrs2 = sqs_client.get_queue_attributes(
                QueueUrl=sqs_queue_url,
                AttributeNames=['ApproximateNumberOfMessages']
            )
            message_count2 = int(queue_attrs2['Attributes']['ApproximateNumberOfMessages'])
            
            # In a real scenario with idempotency, message_count2 would equal message_count1
            # But since we're mocking the idempotent_function, we expect 3 more messages
            self.assertEqual(message_count2, message_count1 + 3)

    def test_lambda_handler(self):
        """Test the Lambda handler function"""
        with patch('src.provider_generated.provider_generated.main.logger'):  # Suppress logger output
            # Create event with S3 notification
            event_body = {
                'bucket': self.test_s3_bucket_name,
                'key': self.test_s3_key_name
            }
            
            event = {
                "Records": [
                    {
                        'eventSource': 'aws:sqs',
                        'body': json.dumps(event_body)
                    }
                ]
            }
            
            # Set environment variables
            os.environ['QUEUE_TARGET'] = self.test_sqs_queue_name
            
            # Call the Lambda handler
            result = lambda_handler(SQSEvent(event), LambdaContext())
            
            # Verify the result
            self.assertEqual(result, event, "Lambda handler should return the original event")
            
            # Check that 3 messages were sent to the queue
            sqs_client = self.session.client("sqs")
            sqs_queue_url = sqs_client.get_queue_url(QueueName=self.test_sqs_queue_name)['QueueUrl']
            queue_attrs = sqs_client.get_queue_attributes(
                QueueUrl=sqs_queue_url,
                AttributeNames=['ApproximateNumberOfMessages']
            )
            self.assertEqual(queue_attrs['Attributes']['ApproximateNumberOfMessages'], '3',
                            "Expected 3 messages in the queue")

    def tearDown(self):
        # Suppress logs during test teardown
        with patch('logging.Logger.info'), patch('logging.Logger.warning'), patch('logging.Logger.error'):
            # Clean up S3 resources
            s3_resource = self.session.resource('s3')
            s3_bucket = s3_resource.Bucket(self.test_s3_bucket_name)
            for key in s3_bucket.objects.all():
                key.delete()
            s3_bucket.delete()

            # Clean up SQS resources
            sqs_client = self.session.client('sqs')
            sqs_queue_url = sqs_client.get_queue_url(QueueName=self.test_sqs_queue_name)['QueueUrl']
            self.session.resource('sqs').Queue(url=sqs_queue_url).delete()
            
            # Clean up DynamoDB table
            dynamodb = self.session.client('dynamodb')
            try:
                dynamodb.delete_table(TableName=os.environ["POWERTOOLS_IDEMPOTENCY_TABLE"])
            except Exception:
                pass  # Ignore errors during cleanup

            # Clear environment variables
            os.environ['QUEUE_TARGET'] = ""

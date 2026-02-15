"""
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

Unit tests for provider_mes

If run local with no local aws credentials, AWS_DEFAULT_REGION must be
set to the environment.
"""

import os
import json
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
    from src.provider_mes.provider_mes.main import (
        lambda_handler,
        process_device_infos_file,
        validate_device_infos,
        build_bulk_importer_message,
        file_key_generator
    )

from .model_provider_mes import LambdaS3Class, LambdaSQSClass


@mock_aws(config={
    "core": {
        "mock_credentials": True,
        "reset_boto3_session": True,
        "service_whitelist": None,
    },
    'iot': {'use_valid_cert': True}})
class TestProviderMes(TestCase):
    """Unit tests for the MES provider module"""
    
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
        """Set up test fixtures"""
        # Suppress logs during test setup
        with patch('logging.Logger.info'), patch('logging.Logger.warning'), patch('logging.Logger.error'):
            self.test_s3_bucket_name = "unit_test_s3_bucket"
            self.test_s3_key_name = "device-infos.json"
            os.environ["S3_BUCKET_NAME"] = self.test_s3_bucket_name
            
            # Create test S3 bucket
            s3_client = self.session.client('s3')
            s3_client.create_bucket(Bucket=self.test_s3_bucket_name)
            
            # Create valid device-infos JSON
            self.valid_device_infos = {
                "batch_id": "batch-001",
                "devices": [
                    {
                        "certFingerprint": "a1b2c3d4e5f67890123456789012345678901234567890123456789012345678",
                        "deviceId": "device-001",
                        "attributes": {
                            "DSN": "DSN123456789",
                            "MAC": "AA:BB:CC:DD:EE:FF"
                        }
                    },
                    {
                        "certFingerprint": "b2c3d4e5f67890123456789012345678901234567890123456789012345678ab",
                        "deviceId": "device-002",
                        "attributes": {
                            "DSN": "DSN987654321",
                            "MAC": "11:22:33:44:55:66"
                        }
                    },
                    {
                        "certFingerprint": "c3d4e5f67890123456789012345678901234567890123456789012345678abcd",
                        "deviceId": "device-003"
                        # No attributes for this device
                    }
                ]
            }
            
            # Upload test file to S3
            s3_client.put_object(
                Bucket=self.test_s3_bucket_name,
                Key=self.test_s3_key_name,
                Body=json.dumps(self.valid_device_infos)
            )
            
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
            "key": "test-key.json"
        }
        key = file_key_generator(test_event, None)
        self.assertIsNotNone(key)
        self.assertEqual(key, "test-bucket:test-key.json")
        
        # Test with invalid input
        invalid_event = {"not_bucket": "data"}
        key = file_key_generator(invalid_event, None)
        self.assertIsNone(key)

    def test_validate_device_infos_valid(self):
        """Test validation with valid device-infos structure"""
        # Should not raise any exception
        try:
            validate_device_infos(self.valid_device_infos)
        except ValueError:
            self.fail("validate_device_infos raised ValueError unexpectedly")

    def test_validate_device_infos_missing_batch_id(self):
        """Test validation fails when batch_id is missing"""
        invalid_data = {
            "devices": []
        }
        with self.assertRaises(ValueError) as context:
            validate_device_infos(invalid_data)
        self.assertIn("batch_id", str(context.exception))

    def test_validate_device_infos_missing_devices(self):
        """Test validation fails when devices array is missing"""
        invalid_data = {
            "batch_id": "batch-001"
        }
        with self.assertRaises(ValueError) as context:
            validate_device_infos(invalid_data)
        self.assertIn("devices", str(context.exception))

    def test_validate_device_infos_empty_devices(self):
        """Test validation fails when devices array is empty"""
        invalid_data = {
            "batch_id": "batch-001",
            "devices": []
        }
        with self.assertRaises(ValueError) as context:
            validate_device_infos(invalid_data)
        self.assertIn("empty", str(context.exception))

    def test_validate_device_infos_missing_fingerprint(self):
        """Test validation fails when certFingerprint is missing"""
        invalid_data = {
            "batch_id": "batch-001",
            "devices": [
                {
                    "deviceId": "device-001"
                }
            ]
        }
        with self.assertRaises(ValueError) as context:
            validate_device_infos(invalid_data)
        self.assertIn("certFingerprint", str(context.exception))

    def test_validate_device_infos_invalid_fingerprint_length(self):
        """Test validation fails when certFingerprint is not 64 chars"""
        invalid_data = {
            "batch_id": "batch-001",
            "devices": [
                {
                    "certFingerprint": "tooshort",
                    "deviceId": "device-001"
                }
            ]
        }
        with self.assertRaises(ValueError) as context:
            validate_device_infos(invalid_data)
        self.assertIn("64 hex chars", str(context.exception))

    def test_validate_device_infos_missing_device_id(self):
        """Test validation fails when deviceId is missing"""
        invalid_data = {
            "batch_id": "batch-001",
            "devices": [
                {
                    "certFingerprint": "a1b2c3d4e5f6789012345678901234567890123456789012345678901234abcd"
                }
            ]
        }
        with self.assertRaises(ValueError) as context:
            validate_device_infos(invalid_data)
        self.assertIn("deviceId", str(context.exception))

    def test_build_bulk_importer_message_with_attributes(self):
        """Test building message with device attributes"""
        device = {
            "certFingerprint": "a1b2c3d4e5f6789012345678901234567890123456789012345678901234abcd",
            "deviceId": "device-001",
            "attributes": {
                "DSN": "DSN123456789",
                "MAC": "AA:BB:CC:DD:EE:FF"
            }
        }
        config = {
            "policies": [{"name": "test-policy", "arn": "arn:aws:iot:us-east-1:123456789012:policy/test-policy"}],
            "thing_groups": [{"name": "test-group", "arn": "arn:aws:iot:us-east-1:123456789012:thinggroup/test-group"}],
            "thing_type_name": "test-type"
        }
        
        message = build_bulk_importer_message(device, config)
        
        self.assertEqual(message['certificate'], device['certFingerprint'])
        self.assertEqual(message['thing'], device['deviceId'])
        self.assertEqual(message['cert_format'], 'FINGERPRINT')
        self.assertEqual(message['thing_deferred'], 'FALSE')
        self.assertEqual(message['policies'], config['policies'])
        self.assertEqual(message['thing_groups'], config['thing_groups'])
        self.assertEqual(message['thing_type_name'], config['thing_type_name'])
        self.assertEqual(message['attributes'], device['attributes'])

    def test_build_bulk_importer_message_without_attributes(self):
        """Test building message without device attributes"""
        device = {
            "certFingerprint": "a1b2c3d4e5f6789012345678901234567890123456789012345678901234abcd",
            "deviceId": "device-001"
        }
        config = {
            "policies": [],
            "thing_groups": []
        }
        
        message = build_bulk_importer_message(device, config)
        
        self.assertEqual(message['certificate'], device['certFingerprint'])
        self.assertEqual(message['thing'], device['deviceId'])
        self.assertEqual(message['cert_format'], 'FINGERPRINT')
        self.assertEqual(message['thing_deferred'], 'FALSE')
        self.assertNotIn('attributes', message)
        self.assertNotIn('thing_type_name', message)

    def test_process_device_infos_file(self):
        """Test processing a device-infos file"""
        with patch('src.provider_mes.provider_mes.main.logger'):  # Suppress logger output
            config = {
                'bucket': self.test_s3_bucket_name,
                'key': self.test_s3_key_name,
                'policies': [{"name": "test-policy", "arn": "arn:aws:iot:us-east-1:123456789012:policy/test-policy"}],
                'thing_groups': []
            }
            sqs_client = self.session.client("sqs")
            sqs_queue_url = sqs_client.get_queue_url(QueueName=self.test_sqs_queue_name)['QueueUrl']

            # Process the device-infos file
            count = process_device_infos_file(config, self.test_sqs_queue_name, self.session)
            
            # Verify that 3 devices were processed
            self.assertEqual(count, 3, "Expected 3 devices to be processed")
            
            # Check that 3 messages were sent to the queue
            queue_attrs = sqs_client.get_queue_attributes(
                QueueUrl=sqs_queue_url,
                AttributeNames=['ApproximateNumberOfMessages']
            )
            self.assertEqual(queue_attrs['Attributes']['ApproximateNumberOfMessages'], '3',
                            "Expected 3 messages in the queue")

    def test_process_device_infos_file_invalid_json(self):
        """Test processing fails with invalid JSON"""
        with patch('src.provider_mes.provider_mes.main.logger'):  # Suppress logger output
            # Upload invalid JSON to S3
            s3_client = self.session.client('s3')
            invalid_key = "invalid.json"
            s3_client.put_object(
                Bucket=self.test_s3_bucket_name,
                Key=invalid_key,
                Body="not valid json"
            )
            
            config = {
                'bucket': self.test_s3_bucket_name,
                'key': invalid_key
            }
            
            # Should raise JSONDecodeError
            with self.assertRaises(json.JSONDecodeError):
                process_device_infos_file(config, self.test_sqs_queue_name, self.session)

    def test_process_device_infos_file_invalid_structure(self):
        """Test processing fails with invalid structure"""
        with patch('src.provider_mes.provider_mes.main.logger'):  # Suppress logger output
            # Upload invalid structure to S3
            s3_client = self.session.client('s3')
            invalid_key = "invalid-structure.json"
            invalid_data = {
                "batch_id": "batch-001"
                # Missing devices array
            }
            s3_client.put_object(
                Bucket=self.test_s3_bucket_name,
                Key=invalid_key,
                Body=json.dumps(invalid_data)
            )
            
            config = {
                'bucket': self.test_s3_bucket_name,
                'key': invalid_key
            }
            
            # Should raise ValueError
            with self.assertRaises(ValueError):
                process_device_infos_file(config, self.test_sqs_queue_name, self.session)

    def test_lambda_handler(self):
        """Test the Lambda handler function"""
        with patch('src.provider_mes.provider_mes.main.logger'):  # Suppress logger output
            # Create event with SQS message
            event_body = {
                'bucket': self.test_s3_bucket_name,
                'key': self.test_s3_key_name,
                'policies': [{"name": "test-policy", "arn": "arn:aws:iot:us-east-1:123456789012:policy/test-policy"}],
                'thing_groups': [{"name": "test-group", "arn": "arn:aws:iot:us-east-1:123456789012:thinggroup/test-group"}]
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
            result = lambda_handler(event, LambdaContext())  # Pass raw dict like AWS sends
            
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
            
            # Verify message content
            messages = sqs_client.receive_message(
                QueueUrl=sqs_queue_url,
                MaxNumberOfMessages=10
            )
            
            self.assertIn('Messages', messages)
            self.assertEqual(len(messages['Messages']), 3)
            
            # Check first message structure
            first_message = json.loads(messages['Messages'][0]['Body'])
            self.assertEqual(first_message['cert_format'], 'FINGERPRINT')
            self.assertEqual(first_message['thing_deferred'], 'FALSE')
            self.assertIn('certificate', first_message)
            self.assertIn('thing', first_message)
            self.assertIn('policies', first_message)
            self.assertIn('thing_groups', first_message)

    def tearDown(self):
        """Clean up test fixtures"""
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

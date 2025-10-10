"""
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

Unit tests for bulk_importer
"""
import os
import base64
import json
import logging
from unittest import TestCase
from unittest.mock import MagicMock, patch
from moto import mock_aws
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from boto3 import _get_default_session
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.utilities.data_classes import SQSEvent
from botocore.exceptions import ClientError

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
    from bulk_importer.main import get_certificate_fingerprint, process_certificate
    from bulk_importer.main import lambda_handler, certificate_key_generator

from .model_bulk_importer import LambdaSQSClass

IOT_POLICY = {
    "Version": "2012-10-17",
    "Statement": [
        {
        "Effect": "Allow",
        "Action": [ "iot:Connect" ],
        "Resource": [
            "arn:aws:iot:us-east-1:123456789012:client/${iot:Connection.Thing.ThingName}"
        ],
        "Condition": {
            "Bool": { "iot:Connection.Thing.IsAttached": "true" }
        }
        }
    ]
}

@mock_aws(config={
    "core": {
        "mock_credentials": True,
        "reset_boto3_session": False,
        "service_whitelist": None,
    },
    'iot': {'use_valid_cert': True}})
class TestBulkImporter(TestCase):
    """Test cases for bulk importer lambda function"""
    def setUp(self):
        # Suppress logs during test setup
        with patch('logging.Logger.info'), patch('logging.Logger.warning'), patch('logging.Logger.error'):
            self.test_sqs_queue_name = "provider"
            sqs_client = _get_default_session().client('sqs')
            sqs_client.create_queue(QueueName=self.test_sqs_queue_name)
            mocked_sqs_resource = _get_default_session().resource("sqs")
            mocked_sqs_resource = { "resource" : _get_default_session().resource('sqs'),
                                    "queue_name" : self.test_sqs_queue_name }
            self.mocked_sqs_class = LambdaSQSClass(mocked_sqs_resource)

            # Create DynamoDB table for idempotency
            dynamodb = _get_default_session().client('dynamodb')
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

            iot_client = _get_default_session().client('iot')
            self.thing_group_arn_solo = (iot_client.create_thing_group(thingGroupName="Thing-Group-Solo"))['thingGroupArn']
            self.thing_group_arn_parent = (iot_client.create_thing_group(thingGroupName="Thing-Group-Parent"))['thingGroupArn']
            self.thing_group_arn_child = (iot_client.create_thing_group(thingGroupName="Thing-Group-Child",
                                                                        parentGroupName="Thing-Group-Parent"))['thingGroupArn']
            self.thing_type_name = "Thingpress-Thing-Type"
            self.thing_type_arn = (iot_client.create_thing_type(thingTypeName=self.thing_type_name))['thingTypeArn']

            self.local_cert = './test/artifacts/single.pem'
            self.local_cert_loaded = None
            with open(self.local_cert, 'rb') as data:
                pem_obj = x509.load_pem_x509_certificate(data.read(),
                                                        backend=default_backend())
                block = pem_obj.public_bytes(encoding=serialization.Encoding.PEM).decode('ascii')
                self.local_cert_loaded = str(base64.b64encode(block.encode('ascii')))

    def test_certificate_key_generator(self):
        """Test the certificate key generator function"""
        # Test with valid input
        test_event = {
            "certificate": "test_certificate_data",
            "thing": "test_thing_name"
        }
        key = certificate_key_generator(test_event, None)
        self.assertIsNotNone(key)
        self.assertTrue(key.startswith("test_thing_name:"))
        
        # Test with invalid input
        invalid_event = {"not_certificate": "data"}
        key = certificate_key_generator(invalid_event, None)
        self.assertIsNone(key)

    def test_pos_process_certificate(self):
        """Positive test case for processing certificate"""
        with open('./test/artifacts/single.pem', 'rb') as data:
            pem_obj = x509.load_pem_x509_certificate(data.read(),
                                                     backend=default_backend())
            block = pem_obj.public_bytes(encoding=serialization.Encoding.PEM).decode('ascii')
            cert = str(base64.b64encode(block.encode('ascii')))
            c = {'certificate': cert, 'thing': 'test-thing'}
            
            # Mock the get_certificate function to simulate certificate not found
            with patch('bulk_importer.main.get_certificate') as mock_get, \
                 patch('bulk_importer.main.logger'):  # Suppress logger output
                mock_get.side_effect = ClientError(
                    {'Error': {'Code': 'ResourceNotFoundException', 'Message': 'Not found'}},
                    'get_certificate'
                )
                
                # Mock register_certificate to return a fixed fingerprint
                with patch('bulk_importer.main.register_certificate') as mock_register, \
                             patch('bulk_importer.main.get_certificate_arn') as mock_arn:

                    fingerprint = get_certificate_fingerprint(pem_obj)
                    mock_register.return_value = fingerprint
                    mock_arn.return_value = "test-certificate-arn"

                    r, arn = process_certificate(c, _get_default_session())
                    self.assertEqual(r, fingerprint)
                    mock_register.assert_called_once()

    def test_idempotency_process_certificate(self):
        """Test idempotency of process_certificate function"""
        # This test verifies that calling process_certificate multiple times with the same input
        # returns the same result without actually processing it again
        
        with patch('bulk_importer.main.register_certificate') as mock_register, \
             patch('bulk_importer.main.get_certificate_arn') as mock_arn, \
             patch('bulk_importer.main.logger'):  # Suppress logger output
            # Mock register_certificate to return a fixed certificate ID
            mock_register.return_value = "test-certificate-id"
            mock_arn.return_value = "test-certificate-arn"

            # First call should process normally
            config = {'certificate': self.local_cert_loaded, 'thing': 'test-thing-idempotent'}
            
            # We need to patch the idempotent_function decorator to simulate its behavior
            with patch('bulk_importer.main.get_certificate') as mock_get:
                # First call should try to get the certificate and fail
                mock_get.side_effect = ClientError(
                    {'Error': {'Code': 'ResourceNotFoundException', 'Message': 'Not found'}},
                    'get_certificate'
                )
                
                result1 = process_certificate(config, _get_default_session())
                
                # Verify register_certificate was called
                mock_register.assert_called_once()
                
                # Reset mocks for second call
                mock_register.reset_mock()
                
                # Second call should find the certificate
                mock_get.side_effect = None
                mock_get.return_value = "test-certificate-id"
                
                result2 = process_certificate(config, _get_default_session())
                
                # Verify register_certificate was not called again
                mock_register.assert_not_called()
                
                # Results should be the same
                self.assertEqual(result1, result2)

    def test_pos_main(self):
        """ Positive test case for the lambda function main entry """
        config = {'certificate': self.local_cert_loaded, 'thing': 'foo'}
        e = { "Records": [{'eventSource': 'aws:sqs', 'body': json.dumps(config)}]}
        os.environ['QUEUE_TARGET']=self.test_sqs_queue_name
        with patch('bulk_importer.main.process_sqs') as mock_process, \
             patch('bulk_importer.main.logger'):  # Suppress logger output
            mock_entry = MagicMock()
            mock_entry.process_sqs.return_value = None
            mock_process.return_value = mock_entry
            v = lambda_handler(e, LambdaContext())  # Pass raw dict like AWS sends
        assert v == e

    def tearDown(self):
        # Suppress logs during test teardown
        with patch('logging.Logger.info'), patch('logging.Logger.warning'), patch('logging.Logger.error'):
            # Clean up SQS resources
            sqs_resource = _get_default_session().resource("sqs", region_name="us-east-1")
            sqs_client = _get_default_session().client("sqs", "us-east-1")
            sqs_queue_url_r = sqs_client.get_queue_url(QueueName=self.test_sqs_queue_name)
            sqs_queue_url = sqs_queue_url_r['QueueUrl']
            sqs_resource = sqs_resource.Queue(url=sqs_queue_url)
            sqs_resource.delete()
            
            # Clean up DynamoDB table
            dynamodb = _get_default_session().client('dynamodb')
            try:
                dynamodb.delete_table(TableName=os.environ["POWERTOOLS_IDEMPOTENCY_TABLE"])
            except Exception:
                pass  # Ignore errors during cleanup


    # ========================================================================
    # v1.0.1 Tests - Multiple Policies and Thing Groups Support
    # ========================================================================

    def test_process_sqs_multiple_policies(self):
        """Test processing SQS message with multiple policies"""
        from bulk_importer.main import process_sqs
        
        # Setup: Create multiple policies
        iot_client = _get_default_session().client('iot')
        iot_client.create_policy(policyName='test-policy-1', policyDocument=json.dumps(IOT_POLICY))
        iot_client.create_policy(policyName='test-policy-2', policyDocument=json.dumps(IOT_POLICY))
        
        # Create config with multiple policies
        config = {
            'certificate': self.local_cert_loaded,
            'thing': 'test-thing-multi-policy',
            'policies': [
                {'name': 'test-policy-1', 'arn': 'arn:aws:iot:us-east-1:123456789012:policy/test-policy-1'},
                {'name': 'test-policy-2', 'arn': 'arn:aws:iot:us-east-1:123456789012:policy/test-policy-2'}
            ]
        }
        
        # Execute
        result = process_sqs(config, session=_get_default_session())
        
        # Verify: Both policies attached to certificate
        cert_id = result['certificate_id']
        cert_arn = f"arn:aws:iot:us-east-1:123456789012:cert/{cert_id}"
        policies = iot_client.list_principal_policies(principal=cert_arn)
        
        self.assertEqual(len(policies['policies']), 2)
        policy_names = [p['policyName'] for p in policies['policies']]
        self.assertIn('test-policy-1', policy_names)
        self.assertIn('test-policy-2', policy_names)

    def test_process_sqs_multiple_thing_groups(self):
        """Test processing SQS message with multiple thing groups"""
        from bulk_importer.main import process_sqs
        
        # Setup: Create thing groups
        iot_client = _get_default_session().client('iot')
        iot_client.create_thing_group(thingGroupName='test-group-1')
        iot_client.create_thing_group(thingGroupName='test-group-2')
        
        # Get ARNs
        group1_arn = iot_client.describe_thing_group(thingGroupName='test-group-1')['thingGroupArn']
        group2_arn = iot_client.describe_thing_group(thingGroupName='test-group-2')['thingGroupArn']
        
        # Create config with multiple thing groups
        config = {
            'certificate': self.local_cert_loaded,
            'thing': 'test-thing-multi-group',
            'thing_groups': [
                {'name': 'test-group-1', 'arn': group1_arn},
                {'name': 'test-group-2', 'arn': group2_arn}
            ]
        }
        
        # Execute
        result = process_sqs(config, session=_get_default_session())
        
        # Verify: Thing is in both groups
        thing_name = result['thing_name']
        groups = iot_client.list_thing_groups_for_thing(thingName=thing_name)
        
        self.assertEqual(len(groups['thingGroups']), 2)
        group_names = [g['groupName'] for g in groups['thingGroups']]
        self.assertIn('test-group-1', group_names)
        self.assertIn('test-group-2', group_names)

    def test_process_sqs_backward_compatibility_legacy_format(self):
        """Test backward compatibility with legacy config format"""
        from bulk_importer.main import process_sqs
        
        # Setup
        iot_client = _get_default_session().client('iot')
        iot_client.create_policy(policyName='legacy-policy', policyDocument=json.dumps(IOT_POLICY))
        iot_client.create_thing_group(thingGroupName='legacy-group')
        group_arn = iot_client.describe_thing_group(thingGroupName='legacy-group')['thingGroupArn']
        
        # Legacy config format (no 'policies' or 'thing_groups' keys)
        config = {
            'certificate': self.local_cert_loaded,
            'thing': 'test-thing-legacy',
            'policy_name': 'legacy-policy',
            'thing_group_arn': group_arn
        }
        
        # Execute
        result = process_sqs(config, session=_get_default_session())
        
        # Verify: Works exactly as before
        cert_id = result['certificate_id']
        cert_arn = f"arn:aws:iot:us-east-1:123456789012:cert/{cert_id}"
        policies = iot_client.list_principal_policies(principal=cert_arn)
        
        self.assertEqual(len(policies['policies']), 1)
        self.assertEqual(policies['policies'][0]['policyName'], 'legacy-policy')
        
        # Verify thing group
        thing_name = result['thing_name']
        groups = iot_client.list_thing_groups_for_thing(thingName=thing_name)
        self.assertEqual(len(groups['thingGroups']), 1)
        self.assertEqual(groups['thingGroups'][0]['groupName'], 'legacy-group')

    def test_process_sqs_empty_lists(self):
        """Test processing with empty policies and thing groups lists"""
        from bulk_importer.main import process_sqs
        
        # Config with empty lists
        config = {
            'certificate': self.local_cert_loaded,
            'thing': 'test-thing-no-attachments',
            'policies': [],
            'thing_groups': [],
            'thing_types': []
        }
        
        # Execute
        result = process_sqs(config, session=_get_default_session())
        
        # Verify: Thing created, but no policies or groups attached
        cert_id = result['certificate_id']
        cert_arn = f"arn:aws:iot:us-east-1:123456789012:cert/{cert_id}"
        policies = _get_default_session().client('iot').list_principal_policies(principal=cert_arn)
        
        self.assertEqual(len(policies['policies']), 0)
        
        # Verify no thing groups
        thing_name = result['thing_name']
        groups = _get_default_session().client('iot').list_thing_groups_for_thing(thingName=thing_name)
        self.assertEqual(len(groups['thingGroups']), 0)

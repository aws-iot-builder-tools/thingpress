#!/usr/bin/env python3
"""
Integration test between certificate_generator and provider_generated modules.

This test verifies that the output from certificate_generator can be properly
processed by provider_generated and prepared for sending to an SQS queue.
"""

import os
import base64
import tempfile
import json
from pathlib import Path
from unittest import TestCase
import pytest

from boto3 import _get_default_session
from moto import mock_aws
from aws_lambda_powertools.utilities.data_classes import SQSEvent
from aws_lambda_powertools.utilities.typing import LambdaContext

# Import the modules under test
from src.certificate_generator.generate_certificates import (
    create_root_ca, create_intermediate_ca, create_end_entity_cert,
    create_certificate_chain
)
from src.provider_generated.provider_generated.main import (
    process_certificate_file, lambda_handler
)
from .model_provider_generated import LambdaS3Class, LambdaSQSClass


@mock_aws(config={
    "core": {
        "mock_credentials": True,
        "reset_boto3_session": True,
        "service_whitelist": None,
    },
    'iot': {'use_valid_cert': True}})
class TestCertificateGeneratorProviderIntegration(TestCase):
    """
    Test the integration between certificate_generator and provider_generated modules.
    """
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
        """Set up test environment."""
        # Create test S3 bucket
        self.test_s3_bucket_name = "test-certificate-bucket"
        self.test_s3_key_name = "certificates_test.txt"
        os.environ["S3_BUCKET_NAME"] = self.test_s3_bucket_name
        
        s3_client = self.session.client('s3')
        s3_client.create_bucket(Bucket=self.test_s3_bucket_name)
        
        mocked_s3_resource = {
            "resource": self.session.resource('s3'),
            "bucket_name": self.test_s3_bucket_name
        }
        self.mocked_s3_class = LambdaS3Class(mocked_s3_resource)

        # Create test SQS queue
        self.test_sqs_queue_name = "test-certificate-queue"
        self.session.client('sqs').create_queue(QueueName=self.test_sqs_queue_name)
        mocked_sqs_resource = {
            "resource": self.session.resource('sqs'),
            "queue_name": self.test_sqs_queue_name
        }
        self.mocked_sqs_class = LambdaSQSClass(mocked_sqs_resource)
        
        # Set environment variables for Lambda
        os.environ['QUEUE_TARGET'] = self.test_sqs_queue_name

    def generate_test_certificates(self, count=3):
        """Generate test certificates using certificate_generator."""
        # Create root CA
        root_cert, root_key = create_root_ca(
            common_name="Test Root CA",
            validity_days=30,
            key_type='ec',
            ec_curve='secp256r1',
            rsa_key_size=2048,
            country="US",
            state="Washington",
            locality="Seattle",
            org="Test Corp",
            org_unit="IoT Division"
        )
        
        # Create intermediate CA
        int_cert, int_key = create_intermediate_ca(
            common_name="Test Intermediate CA",
            validity_days=30,
            key_type='ec',
            ec_curve='secp256r1',
            rsa_key_size=2048,
            country="US",
            state="Washington",
            locality="Seattle",
            org="Test Corp",
            org_unit="IoT Division",
            root_ca=root_cert,
            root_ca_key=root_key
        )
        
        # Generate end-entity certificates with predictable CNs
        certificates = []
        for i in range(count):
            common_name = f"Device-{i+1}"
            end_cert, _ = create_end_entity_cert(
                common_name=common_name,
                validity_days=30,
                key_type='ec',
                ec_curve='secp256r1',
                rsa_key_size=2048,
                country="US",
                state="Washington",
                locality="Seattle",
                org="Test Corp",
                org_unit="IoT Division",
                intermediate_ca=int_cert,
                intermediate_ca_key=int_key
            )
            
            # Create certificate chain
            cert_chain = create_certificate_chain(end_cert, int_cert, root_cert)
            
            # Base64 encode the certificate chain
            encoded_chain = base64.b64encode(cert_chain).decode('utf-8')
            certificates.append(encoded_chain)
        
        return certificates

    def test_certificate_generator_to_provider_generated_integration(self):
        """
        Test that certificates generated by certificate_generator can be
        processed by provider_generated and prepared for SQS.
        """
        # Generate test certificates
        certificates = self.generate_test_certificates(count=3)
        
        # Create a certificate file in S3
        s3_client = self.session.client('s3')
        s3_client.put_object(
            Bucket=self.test_s3_bucket_name,
            Key=self.test_s3_key_name,
            Body='\n'.join(certificates)
        )
        
        # Create config for processing
        config = {
            'bucket': self.test_s3_bucket_name,
            'key': self.test_s3_key_name
        }
        
        # Process the certificate file
        count = process_certificate_file(config, self.test_sqs_queue_name, self.session)
        
        # Verify that all certificates were processed
        self.assertEqual(count, 3, "Expected 3 certificates to be processed")
        
        # Check that messages were sent to the queue
        sqs_client = self.session.client("sqs")
        sqs_queue_url = sqs_client.get_queue_url(QueueName=self.test_sqs_queue_name)['QueueUrl']
        queue_attrs = sqs_client.get_queue_attributes(
            QueueUrl=sqs_queue_url,
            AttributeNames=['ApproximateNumberOfMessages']
        )
        self.assertEqual(queue_attrs['Attributes']['ApproximateNumberOfMessages'], '3',
                         "Expected 3 messages in the queue")
        
        # Receive messages from the queue and verify their content
        messages = sqs_client.receive_message(
            QueueUrl=sqs_queue_url,
            MaxNumberOfMessages=10
        )
        
        self.assertIn('Messages', messages, "Expected messages in the queue")
        self.assertEqual(len(messages['Messages']), 3, "Expected 3 messages in the queue")
        
        # Verify each message contains the expected data
        for i, message in enumerate(messages['Messages']):
            body = json.loads(message['Body'])
            
            # Check that the message contains the required fields
            self.assertIn('certificate', body, "Message should contain certificate data")
            self.assertIn('thing', body, "Message should contain thing name")
            self.assertIn('bucket', body, "Message should contain bucket name")
            self.assertIn('key', body, "Message should contain key name")
            
            # Verify the thing name matches the expected pattern
            self.assertTrue(body['thing'].startswith("Device-"), 
                           f"Thing name should start with 'Device-', got {body['thing']}")
            
            cert_bytes = base64.b64decode(certificates[i])
            post_process_certificate = str(base64.b64encode(str(cert_bytes).encode('ascii')))
            # Verify the certificate data is the same as what we generated
            self.assertEqual(body['certificate'], post_process_certificate,
                            "Certificate data in message should match generated certificate")

    def test_lambda_handler_with_generated_certificates(self):
        """
        Test the Lambda handler with certificates generated by certificate_generator.
        """
        # Generate test certificates
        certificates = self.generate_test_certificates(count=3)
        
        # Create a certificate file in S3
        s3_client = self.session.client('s3')
        s3_client.put_object(
            Bucket=self.test_s3_bucket_name,
            Key=self.test_s3_key_name,
            Body='\n'.join(certificates)
        )
        
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
        
        # Call the Lambda handler
        result = lambda_handler(event, LambdaContext())  # Pass raw dict like AWS sends
        
        # Verify the result
        self.assertEqual(result, event, "Lambda handler should return the original event")
        
        # Check that messages were sent to the queue
        sqs_client = self.session.client("sqs")
        sqs_queue_url = sqs_client.get_queue_url(QueueName=self.test_sqs_queue_name)['QueueUrl']
        queue_attrs = sqs_client.get_queue_attributes(
            QueueUrl=sqs_queue_url,
            AttributeNames=['ApproximateNumberOfMessages']
        )
        self.assertEqual(queue_attrs['Attributes']['ApproximateNumberOfMessages'], '3',
                         "Expected 3 messages in the queue")

    def tearDown(self):
        """Clean up test resources."""
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

        # Clear environment variables
        os.environ['QUEUE_TARGET'] = ""

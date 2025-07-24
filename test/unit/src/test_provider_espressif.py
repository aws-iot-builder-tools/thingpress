"""
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

Unit tests for provider_espressif

If run local with no local aws credentials, AWS_DEFAULT_REGION must be
set to the environment.
"""


import os
import json
from unittest import TestCase

from boto3 import _get_default_session
from moto import mock_aws
from aws_lambda_powertools.utilities.data_classes import SQSEvent
from aws_lambda_powertools.utilities.typing import LambdaContext

from src.provider_espressif.main import lambda_handler, invoke_export
from .model_provider_espressif import LambdaS3Class, LambdaSQSClass

@mock_aws(config={
    "core": {
        "mock_credentials": True,
        "reset_boto3_session": True,
        "service_whitelist": None,
    },
    'iot': {'use_valid_cert': True}})
class TestProviderEspressif(TestCase):
    """Unit tests for the espressif provider module"""
    def __init__(self, x):
        super().__init__(x)

        # Session management across all tests
        os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
        os.environ["AWS_REGION"] = "us-east-1"
        os.environ["AWS_ACCESS_KEY_ID"] = "testing"
        os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
        os.environ["AWS_SECURITY_TOKEN"] = "testing"
        os.environ["AWS_SESSION_TOKEN"] = "testing"
        self.session = _get_default_session()

    def setUp(self):
        self.test_s3_bucket_name = "unit_test_s3_bucket"
        self.test_s3_key_name = "manifest.csv"
        self.test_s3_object_content = None
        os.environ["S3_BUCKET_NAME"] = self.test_s3_bucket_name
        s3_client = self.session.client('s3')
        s3_client.create_bucket(Bucket = self.test_s3_bucket_name )
        with open('./test/artifacts/manifest-espressif.csv', 'rb') as data:
            s3_client.put_object(Bucket=self.test_s3_bucket_name, Key=self.test_s3_key_name, Body=data)
            self.test_s3_object_content = s3_client.get_object(Bucket=self.test_s3_bucket_name, Key=self.test_s3_key_name)['Body']
        mocked_s3_resource = { "resource" : self.session.resource('s3'),
                               "bucket_name" : self.test_s3_bucket_name }
        self.mocked_s3_class = LambdaS3Class(mocked_s3_resource)

        self.test_sqs_queue_name = "provider"

        self.session.client('sqs').create_queue(QueueName=self.test_sqs_queue_name)
        mocked_sqs_resource = { "resource" : self.session.resource('sqs'),
                                "queue_name" : self.test_sqs_queue_name }
        self.mocked_sqs_class = LambdaSQSClass(mocked_sqs_resource)

    def test_pos_invoke_export(self):
        """ The number of items in the queue should be 7 since there are
            seven certificates in the test file """
        config = {
            'bucket': self.test_s3_bucket_name,
            'key': self.test_s3_key_name
        }
        sqs_client = self.session.client("sqs")
        sqs_queue_url = sqs_client.get_queue_url(QueueName=self.test_sqs_queue_name)['QueueUrl']

        invoke_export(config, "provider", self.session)
        p = sqs_client.get_queue_attributes(QueueUrl=sqs_queue_url,
                                            AttributeNames=['ApproximateNumberOfMessages'])
        assert p['Attributes']['ApproximateNumberOfMessages'] == '7'

    def test_pos_lambda_handler_1(self):
        """Invoke the main handler with one file"""
        r1 = {
            'policy_arn': 'dev_policy',
            'bucket': self.test_s3_bucket_name,
            'key': self.test_s3_key_name
        }

        e = { "Records": [{
                    'eventSource': 'aws:sqs',
                    'body': json.dumps(r1)
                }]
            }
        os.environ['QUEUE_TARGET'] = self.test_sqs_queue_name
        v = lambda_handler(e, LambdaContext())  # Pass raw dict like AWS sends
        assert v == e

    def tearDown(self):
        s3_resource = self.session.resource('s3')
        s3_bucket = s3_resource.Bucket( self.test_s3_bucket_name )
        for key in s3_bucket.objects.all():
            key.delete()
        s3_bucket.delete()

        sqs_client = self.session.client('sqs')
        sqs_queue_url_r = sqs_client.get_queue_url(QueueName=self.test_sqs_queue_name)
        sqs_queue_url = sqs_queue_url_r['QueueUrl']
        self.session.resource('sqs').Queue(url=sqs_queue_url).delete()

        os.environ['QUEUE_TARGET']=""

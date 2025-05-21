"""
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

Unit tests for bulk_importer
"""
import os
import base64
import copy
import json
from unittest import TestCase
from moto import mock_aws
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from boto3 import resource, client
from src.product_provider.main import lambda_handler, process

from .model_bulk_importer import LambdaSQSClass

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
        self.test_sqs_queue_name = "provider"
        sqs_client = client('sqs', region_name="us-east-1")
        sqs_client.create_queue(QueueName=self.test_sqs_queue_name)
        mocked_sqs_resource = resource("sqs")
        mocked_sqs_resource = { "resource" : resource('sqs'),
                                "queue_name" : self.test_sqs_queue_name }
        self.mocked_sqs_class = LambdaSQSClass(mocked_sqs_resource)

    def test_pos_process_1(self):
        """Positive test case for processing certificate"""
        with open('./test/artifacts/single.pem', 'rb') as data:
            pem_obj = x509.load_pem_x509_certificate(data.read(),
                                                     backend=default_backend())
            block = pem_obj.public_bytes(encoding=serialization.Encoding.PEM).decode('ascii')
            cert = str(base64.b64encode(block.encode('ascii')))
            c = {'certificate': cert}
            d = copy.deepcopy(c)
            d['policy_name'] = "my_policy"
            d['thing_group_name'] = "my_thing_group"
            d['thing_type_name'] = "my_thing_type"

            os.environ['QUEUE_TARGET'] = self.test_sqs_queue_name
            os.environ['POLICY_NAME'] = d['policy_name']
            os.environ['THING_GROUP_NAME'] = d['thing_group_name']
            os.environ['THING_TYPE_NAME'] = d['thing_type_name']
            r = process(c)
            assert r == d

    def test_pos_process_2(self):
        """Positive test case for processing certificate"""
        with open('./test/artifacts/single.pem', 'rb') as data:
            pem_obj = x509.load_pem_x509_certificate(data.read(),
                                                     backend=default_backend())
            block = pem_obj.public_bytes(encoding=serialization.Encoding.PEM).decode('ascii')
            cert = str(base64.b64encode(block.encode('ascii')))
            c = {'certificate': cert}
            d = copy.deepcopy(c)
            d['policy_name'] = "my_policy"
            d['thing_group_name'] = None
            d['thing_type_name'] = None

            os.environ['QUEUE_TARGET'] = self.test_sqs_queue_name
            os.environ['POLICY_NAME'] = d['policy_name']
            os.environ['THING_GROUP_NAME'] = "None"
            os.environ['THING_TYPE_NAME'] = "None"
            r = process(c)
            assert r == d

    def test_pos_lambda_handler(self):
        rcd = { "Records": [
                {
                "messageId": "059f36b4-87a3-44ab-83d2-661975830a7d",
                "receiptHandle": "AQEBwJnKyrHigUMZj6rYigCgxlaS3SLy0a...",
                "body": "Test message.",
                "attributes": {
                "ApproximateReceiveCount": "1",
                "SentTimestamp": "1545082649183",
                "SenderId": "AIDAIENQZJOLO23YVJ4VO",
                "ApproximateFirstReceiveTimestamp": "1545082649185"
                },
                "messageAttributes": {},
                "md5OfBody": "e4e68fb7bd0e697a0ae8f1bb342846b3",
                "eventSource": "aws:sqs",
                "eventSourceARN": "arn:aws:sqs:us-east-2:123456789012:my-queue",
                "awsRegion": "us-east-2"
                },
            ]
        }

        with open('./test/artifacts/single.pem', 'rb') as data:
            pem_obj = x509.load_pem_x509_certificate(data.read(),
                                                     backend=default_backend())
            block = pem_obj.public_bytes(encoding=serialization.Encoding.PEM).decode('ascii')
            cert = str(base64.b64encode(block.encode('ascii')))
            c = {'certificate': cert}
            rcd['Records'][0]['body'] = json.dumps(c)
            d = copy.deepcopy(c)
            d['policy_name'] = "my_policy"
            d['thing_group_name'] = "my_thing_group"
            d['thing_type_name'] = "my_thing_type"
            os.environ['QUEUE_TARGET'] = self.test_sqs_queue_name
            os.environ['POLICY_NAME'] = d['policy_name']
            os.environ['THING_GROUP_NAME'] = d['thing_group_name']
            os.environ['THING_TYPE_NAME'] = d['thing_type_name']
            r = lambda_handler(rcd, None)
            # The result is an array of processed records, so our fabricated certificate
            # needs to be in array context
            assert r == [d]

    def tearDown(self):
        sqs_resource = resource("sqs", region_name="us-east-1")
        sqs_client = client("sqs", "us-east-1")
        sqs_queue_url_r = sqs_client.get_queue_url(QueueName=self.test_sqs_queue_name)
        sqs_queue_url = sqs_queue_url_r['QueueUrl']
        sqs_resource = sqs_resource.Queue(url=sqs_queue_url)
        sqs_resource.delete()

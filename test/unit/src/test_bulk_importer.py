"""
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

Unit tests for bulk_importer
"""
import os
import base64
import json
from unittest import TestCase
from unittest.mock import MagicMock, patch
from moto import mock_aws
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from boto3 import _get_default_session
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.utilities.data_classes import SQSEvent
from src.bulk_importer.main import get_certificate_fingerprint, process_certificate
from src.bulk_importer.main import lambda_handler
from .model_bulk_importer import LambdaSQSClass

# Ensure that we are not using real AWS credentials
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
os.environ["AWS_REGION"] = "us-east-1"
os.environ["AWS_ACCESS_KEY_ID"] = "testing"
os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
os.environ["AWS_SECURITY_TOKEN"] = "testing"
os.environ["AWS_SESSION_TOKEN"] = "testing"

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
        self.test_sqs_queue_name = "provider"
        sqs_client = _get_default_session().client('sqs')
        sqs_client.create_queue(QueueName=self.test_sqs_queue_name)
        mocked_sqs_resource = _get_default_session().resource("sqs")
        mocked_sqs_resource = { "resource" : _get_default_session().resource('sqs'),
                                "queue_name" : self.test_sqs_queue_name }
        self.mocked_sqs_class = LambdaSQSClass(mocked_sqs_resource)

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

    def test_pos_process_certificate(self):
        """Positive test case for processing certificate"""
        with open('./test/artifacts/single.pem', 'rb') as data:
            pem_obj = x509.load_pem_x509_certificate(data.read(),
                                                     backend=default_backend())
            block = pem_obj.public_bytes(encoding=serialization.Encoding.PEM).decode('ascii')
            cert = str(base64.b64encode(block.encode('ascii')))
            c = {'certificate': cert}
            r = process_certificate(c, _get_default_session())
            assert r == get_certificate_fingerprint(pem_obj)

    def test_pos_main(self):
        """ Positive test case for the lambda function main entry """
        config = {'certificate': self.local_cert_loaded, 'thing': 'foo'}
        e = { "Records": [{'eventSource': 'aws:sqs', 'body': json.dumps(config)}]}
        os.environ['QUEUE_TARGET']=self.test_sqs_queue_name
        with patch('src.bulk_importer.main.process_sqs') as mock_process:
            mock_entry = MagicMock()
            mock_entry.process_sqs.return_value = None
            mock_process.return_value = mock_entry
            v = lambda_handler(SQSEvent(e), LambdaContext())
        assert v == e

    def tearDown(self):
        sqs_resource = _get_default_session().resource("sqs", region_name="us-east-1")
        sqs_client = _get_default_session().client("sqs", "us-east-1")
        sqs_queue_url_r = sqs_client.get_queue_url(QueueName=self.test_sqs_queue_name)
        sqs_queue_url = sqs_queue_url_r['QueueUrl']
        sqs_resource = sqs_resource.Queue(url=sqs_queue_url)
        sqs_resource.delete()

"""
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

Unit tests for bulk_importer
"""
import base64
import json
from unittest import TestCase
from pytest import raises
from moto import mock_aws
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from botocore.exceptions import ClientError
from boto3 import resource, client
from src.bulk_importer.main import get_certificate_fingerprint, requeue, process_certificate
from src.bulk_importer.main import get_certificate_arn, get_thing, get_policy, get_thing_group
from src.bulk_importer.main import get_thing_type, process_policy, process_thing
#    from src.bulk_importer.main import lambda_handler
#    from src.bulk_importer.main import get_certificate_arn, get_thing_type
#    from src.bulk_importer.main import process_thing_group, get_name_from_certificate, process_sqs
from .model_bulk_importer import LambdaSQSClass

POLICY = {
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
        sqs_client = client('sqs')
        sqs_client.create_queue(QueueName=self.test_sqs_queue_name)
        mocked_sqs_resource = resource("sqs")
        mocked_sqs_resource = { "resource" : resource('sqs'),
                                "queue_name" : self.test_sqs_queue_name }
        self.mocked_sqs_class = LambdaSQSClass(mocked_sqs_resource)

    def test_pos_process_certificate(self):
        """Positive test case for processing certificate"""
        with open('./test/artifacts/single.pem', 'rb') as data:
            pem_obj = x509.load_pem_x509_certificate(data.read(),
                                                     backend=default_backend())
            block = pem_obj.public_bytes(encoding=serialization.Encoding.PEM).decode('ascii')
            cert = str(base64.b64encode(block.encode('ascii')))
            c = {'certificate': cert}
            r = process_certificate(c, requeue)
            assert r == get_certificate_fingerprint(pem_obj)

    def test_pos_get_certificate_arn(self):
        """Positive test for get_certificate_arn"""
        with open('./test/artifacts/single.pem', 'rb') as data:
            pem_obj = x509.load_pem_x509_certificate(data.read(),
                                                     backend=default_backend())
        certificate_id = get_certificate_fingerprint(pem_obj)
        block = pem_obj.public_bytes(encoding=serialization.Encoding.PEM).decode('ascii')
        cert = str(base64.b64encode(block.encode('ascii')))
        r = process_certificate({'certificate':cert}, requeue)
        r = get_certificate_arn(certificate_id)
        assert r is not None

    def test_neg_get_certificate_arn(self):
        """Negative test for get_certificate_arn"""

        with raises(ClientError) as exc:
            get_certificate_arn("9"*64)
        err = exc.value.response['Error']
        assert err['Code'] == 'ResourceNotFoundException'

    def test_pos_get_thing(self):
        """Positive test case to return thing arn"""
        iot_client = client('iot')
        n = "test_pos_get_thing"
        r1 = iot_client.create_thing(thingName=n)
        r2 = get_thing(n)
        assert r1['thingArn'] == r2

    def test_pos_get_policy(self):
        """Positive test case to return policy arn"""
        iot_client = client('iot')
        n = "test_pos_get_policy"
        p = json.dumps(POLICY)
        r1 = iot_client.create_policy(policyName=n, policyDocument=p)
        r2 = get_policy(n)
        assert r1['policyArn'] == r2

    def test_pos_get_thing_group(self):
        """Positive test case to return thing group arn"""
        iot_client = client('iot')
        n = "test_pos_get_thing_group"
        r1 = iot_client.create_thing_group(thingGroupName=n)
        r2 = get_thing_group(thing_group_name=n)
        assert r1['thingGroupArn'] == r2

    def test_pos_get_thing_type(self):
        """Positive test case to return thing type arn"""
        n = "test_pos_get_thing_type"
        iot_client = client('iot')
        r1 = iot_client.create_thing_type(thingTypeName=n)
        r2 = get_thing_type(type_name=n)
        assert r1['thingTypeArn'] == r2

    def test_pos_process_policy(self):
        """Positive test case for attaching policy to certificate"""
        iot_client = client('iot')
        with open('./test/artifacts/single.pem', 'rb') as data:
            pem_obj = x509.load_pem_x509_certificate(data.read(),
                                                     backend=default_backend())
            block = pem_obj.public_bytes(encoding=serialization.Encoding.PEM).decode('ascii')
            cert = str(base64.b64encode(block.encode('ascii')))
            c = {'certificate': cert}
            cr = process_certificate(c, requeue)
            n = "process_policy"
            p = json.dumps(POLICY)
            iot_client.create_policy(policyName=n, policyDocument=p)
            process_policy(n, cr)

    def test_pos_process_thing(self):
        """Positive test case for attaching policy to certificate"""
        iot_client = client('iot')
        with open('./test/artifacts/single.pem', 'rb') as data:
            pem_obj = x509.load_pem_x509_certificate(data.read(),
                                                     backend=default_backend())
            block = pem_obj.public_bytes(encoding=serialization.Encoding.PEM).decode('ascii')
            cert = str(base64.b64encode(block.encode('ascii')))
            c = {'certificate': cert}
            cr = process_certificate(c, requeue)
            n = "process_thing"
            iot_client.create_thing(thingName=n)
            process_thing(n, cr)

    def test_pos_requeue(self):
        pass
    def test_pos_get_certificate_fingerprint(self):
        with open('./test/artifacts/single.pem', 'rb') as data:
            pem_obj = x509.load_pem_x509_certificate(data.read(),
                                                     backend=default_backend())
            get_certificate_fingerprint(pem_obj)

    def test_pos_process_thing_group(self):
        pass

    def tearDown(self):
        sqs_resource = resource("sqs", region_name="us-east-1")
        sqs_client = client("sqs", "us-east-1")
        sqs_queue_url_r = sqs_client.get_queue_url(QueueName=self.test_sqs_queue_name)
        sqs_queue_url = sqs_queue_url_r['QueueUrl']
        sqs_resource = sqs_resource.Queue(url=sqs_queue_url)
        sqs_resource.delete()

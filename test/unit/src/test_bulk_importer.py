"""
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

Unit tests for bulk_importer
"""
import os
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
from src.bulk_importer.main import get_certificate_arn, process_policy, process_thing, lambda_handler
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
        self.test_sqs_queue_name = "provider"
        sqs_client = client('sqs')
        sqs_client.create_queue(QueueName=self.test_sqs_queue_name)
        mocked_sqs_resource = resource("sqs")
        mocked_sqs_resource = { "resource" : resource('sqs'),
                                "queue_name" : self.test_sqs_queue_name }
        self.mocked_sqs_class = LambdaSQSClass(mocked_sqs_resource)

        iot_client = client('iot')
        self.thing_group_arn_solo = (iot_client.create_thing_group(thingGroupName="Thing-Group-Solo"))['thingGroupArn']
        self.thing_group_arn_parent = (iot_client.create_thing_group(thingGroupName="Thing-Group-Parent"))['thingGroupArn']
        # BUG: Moto has problem with parent/child at the moment
        #self.thing_group_arn_child = (iot_client.create_thing_group(thingGroupName="Thing-Group-Child", parentGroupName="Thing Group Parent"))['thingGroupArn']
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
            p = json.dumps(IOT_POLICY)
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
            x = process_thing(n, cr)
            assert x is True

    def test_pos_process_thing_with_type(self):
        """Positive test case for attaching policy to certificate"""
        iot_client = client('iot')
        c = { 'certificate': self.local_cert_loaded}
        cr = process_certificate(c, requeue)
        n = "process_thing"
        iot_client.create_thing(thingName=n)
        x = process_thing(n, cr, self.thing_type_name)
        assert x is True

    def test_pos_process_thing_no_prev_thing(self):
        """Positive test case for attaching policy to certificate"""
        c = {'certificate': self.local_cert_loaded}
        cr = process_certificate(c, requeue)
        n = "process_thing"
        x = process_thing(n, cr)
        assert x is True

    def test_pos_process_thing_with_type_no_prev_thing(self):
        """Positive test case for attaching policy to certificate"""
        c = {'certificate': self.local_cert_loaded}
        cr = process_certificate(c, requeue)
        n = "process_thing"
        x = process_thing(n, cr, self.thing_type_name)
        assert x is True

    def test_pos_requeue(self):
        pass
    def test_pos_get_certificate_fingerprint(self):
        with open('./test/artifacts/single.pem', 'rb') as data:
            pem_obj = x509.load_pem_x509_certificate(data.read(),
                                                     backend=default_backend())
            get_certificate_fingerprint(pem_obj)

    def test_pos_process_thing_group(self):
        pass

    def test_pos_main(self):
        config = {'certificate': self.local_cert_loaded,
                  'thing': 'foo'}
        e = { "Records": [{
                'eventSource': 'aws:sqs',
                'body': json.dumps(config)
            }
            ]}
        os.environ['QUEUE_TARGET']=self.test_sqs_queue_name
        c = None
        v = lambda_handler(e, c)
        assert v == e

    def tearDown(self):
        sqs_resource = resource("sqs", region_name="us-east-1")
        sqs_client = client("sqs", "us-east-1")
        sqs_queue_url_r = sqs_client.get_queue_url(QueueName=self.test_sqs_queue_name)
        sqs_queue_url = sqs_queue_url_r['QueueUrl']
        sqs_resource = sqs_resource.Queue(url=sqs_queue_url)
        sqs_resource.delete()

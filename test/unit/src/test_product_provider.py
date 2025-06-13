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
from pytest import raises
from moto import mock_aws

from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from boto3 import resource, client
from src.product_provider.main import lambda_handler, process, get_provider_queue

from .model_product_provider import LambdaS3Class, LambdaSQSClass

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
        self.obj_dir = "./test/artifacts/"
        self.obj_espressif = "manifest-espressif.csv"
        self.obj_infineon = "manifest-infineon.7z"
        self.obj_microchip = "ECC608C-TNGTLSU-B.json"
        self.bucket_espressif_pos = "thingpress-espressif-stackname"
        self.bucket_espressif_neg = "thingpress-espressi-stackname"
        self.bucket_infineon_pos = "thingpress-infineon-stackname"
        self.bucket_infineon_neg = "thingpress-infineo-stackname"
        self.bucket_microchip_pos = "thingpress-microchip-stackname"
        self.bucket_microchip_neg = "thingpress-microchi-stackname"

        self.obj_espressif_local = self.obj_dir + self.obj_espressif
        self.obj_infineon_local = self.obj_dir + self.obj_infineon
        self.obj_microchip_local = self.obj_dir + self.obj_microchip

        # QUEUE_TARGET_ESPRESSIF
        self.env_queue_target_espressif = "Thingpress-Espressif-Provider-stackname"
        # QUEUE_TARGET_INFINEON
        self.env_queue_target_infineon = "Thingpress-Infineon-Provider-stackname"
        # QUEUE_TARGET_MICROCHIP
        self.env_queue_target_microchip = "Thingpress-Microchip-Provider-stackname"
        # env: POLICY_NAME
        self.env_policy_name_pos = "myPolicy"
        self.env_policy_name_neg = "myBadPolicy"
        # env: THING_GROUP_NAME
        self.env_thing_group_name_pos = "myThingGroup"
        self.env_thing_group_name_neg = "myBadThingGroup"
        # env: THING_TYPE_NAME
        self.env_thing_type_name_pos = "myThingType"
        self.env_thing_type_name_neg = "myBadThingType"

        s3_client = client('s3', region_name="us-east-1")

        s3_client.create_bucket(Bucket = self.bucket_espressif_pos )
        s3_client.create_bucket(Bucket = self.bucket_espressif_neg )
        s3_client.create_bucket(Bucket = self.bucket_infineon_pos )
        s3_client.create_bucket(Bucket = self.bucket_infineon_neg )
        s3_client.create_bucket(Bucket = self.bucket_microchip_pos )
        s3_client.create_bucket(Bucket = self.bucket_microchip_neg )

        self.mocked_s3_espressif_pos = LambdaS3Class({
            "resource" : resource('s3'),
            "bucket_name" : self.bucket_espressif_pos })

        with open(self.obj_espressif_local, 'rb') as data:
            s3_client.put_object(Bucket=self.bucket_espressif_pos,
                                 Key=self.obj_espressif,
                                 Body=data)


        self.test_sqs_queue_name = "provider"
        sqs_client = client('sqs', region_name="us-east-1")
        sqs_client.create_queue(QueueName=self.test_sqs_queue_name)
        mocked_sqs_resource = resource("sqs")
        mocked_sqs_resource = { "resource" : resource('sqs'),
                                "queue_name" : self.test_sqs_queue_name }
        self.mocked_sqs_class = LambdaSQSClass(mocked_sqs_resource)

    def test_gpq_espressif_pos(self):
        os.environ['QUEUE_TARGET_ESPRESSIF'] = self.env_queue_target_espressif
        assert get_provider_queue(self.bucket_espressif_pos) == self.env_queue_target_espressif
    def test_gpq_infineon_pos(self):
        os.environ['QUEUE_TARGET_INFINEON'] = self.env_queue_target_infineon
        assert get_provider_queue(self.bucket_infineon_pos) == self.env_queue_target_infineon
    def test_gpq_microchip_pos(self):
        os.environ['QUEUE_TARGET_MICROCHIP'] = self.env_queue_target_microchip
        assert get_provider_queue(self.bucket_microchip_pos) == self.env_queue_target_microchip

    def test_gpq_espressif_neg(self):
        os.environ['QUEUE_TARGET_ESPRESSIF'] = self.env_queue_target_espressif
        assert get_provider_queue(self.bucket_espressif_neg) is None
    def test_gpq_infineon_neg(self):
        os.environ['QUEUE_TARGET_INFINEON'] = self.env_queue_target_infineon
        assert get_provider_queue(self.bucket_infineon_neg) is None
    def test_gpq_microchip_neg(self):
        os.environ['QUEUE_TARGET_MICROCHIP'] = self.env_queue_target_microchip
        assert get_provider_queue(self.bucket_microchip_neg) is None




#    def test_pos_process_2(self):
#        """Bucket and object must be accessible"""



#        with open('./test/artifacts/single.pem', 'rb') as data:
#            pem_obj = x509.load_pem_x509_certificate(data.read(),
#                                                     backend=default_backend())
#            block = pem_obj.public_bytes(encoding=serialization.Encoding.PEM).decode('ascii')
#            cert = str(base64.b64encode(block.encode('ascii')))
#            c = {'certificate': cert}
#            d = copy.deepcopy(c)
#            d['policy_name'] = "my_policy"
#            d['thing_group_name'] = "my_thing_group"
#            d['thing_type_name'] = "my_thing_type"
#
#            os.environ['QUEUE_TARGET'] = self.test_sqs_queue_name
#            os.environ['POLICY_NAME'] = d['policy_name']
#            os.environ['THING_GROUP_NAME'] = d['thing_group_name']
#            os.environ['THING_TYPE_NAME'] = d['thing_type_name']
#            r = process(c)
#            assert r == d

#    def test_pos_process_2(self):
#        """Positive test case for processing certificate"""
#        with open('./test/artifacts/single.pem', 'rb') as data:
#            pem_obj = x509.load_pem_x509_certificate(data.read(),
#                                                     backend=default_backend())
#            block = pem_obj.public_bytes(encoding=serialization.Encoding.PEM).decode('ascii')
#            cert = str(base64.b64encode(block.encode('ascii')))
#            c = {'certificate': cert}
#            d = copy.deepcopy(c)
#            d['policy_name'] = "my_policy"
#            d['thing_group_name'] = None
#            d['thing_type_name'] = None
#
#            os.environ['QUEUE_TARGET'] = self.test_sqs_queue_name
#            os.environ['POLICY_NAME'] = d['policy_name']
#            os.environ['THING_GROUP_NAME'] = "None"
#            os.environ['THING_TYPE_NAME'] = "None"
#            r = process(c)
#            assert r == d

#    def test_pos_lambda_handler(self):
#        """Invoke with an sqs event"""
#        rcd = { "Records": [
#                {
#                "messageId": "059f36b4-87a3-44ab-83d2-661975830a7d",
#                "receiptHandle": "AQEBwJnKyrHigUMZj6rYigCgxlaS3SLy0a...",
#                "body": "Test message.",
#                "attributes": {
#                "ApproximateReceiveCount": "1",
#                "SentTimestamp": "1545082649183",
#                "SenderId": "AIDAIENQZJOLO23YVJ4VO",
#                "ApproximateFirstReceiveTimestamp": "1545082649185"
#                },
#                "messageAttributes": {},
#                "md5OfBody": "e4e68fb7bd0e697a0ae8f1bb342846b3",
#                "eventSource": "aws:sqs",
#                "eventSourceARN": "arn:aws:sqs:us-east-2:123456789012:my-queue",
#                "awsRegion": "us-east-2"
#                },
#            ]
#        }
#
#        with open('./test/artifacts/single.pem', 'rb') as data:
#            pem_obj = x509.load_pem_x509_certificate(data.read(),
#                                                     backend=default_backend())
#            block = pem_obj.public_bytes(encoding=serialization.Encoding.PEM).decode('ascii')
#            cert = str(base64.b64encode(block.encode('ascii')))
#            c = {'certificate': cert}
#            rcd['Records'][0]['body'] = json.dumps(c)
#            d = copy.deepcopy(c)
#            d['policy_name'] = "my_policy"
#            d['thing_group_name'] = "my_thing_group"
#            d['thing_type_name'] = "my_thing_type"
#            os.environ['QUEUE_TARGET'] = self.test_sqs_queue_name
#            os.environ['POLICY_NAME'] = d['policy_name']
#            os.environ['THING_GROUP_NAME'] = d['thing_group_name']
#            os.environ['THING_TYPE_NAME'] = d['thing_type_name']
#            r = lambda_handler(rcd, None)
#            # The result is an array of processed records, so our fabricated certificate
#            # needs to be in array context
#            assert r == [d]

    def tearDown(self):
        sqs_resource = resource("sqs", region_name="us-east-1")
        sqs_client = client("sqs", "us-east-1")
        sqs_queue_url_r = sqs_client.get_queue_url(QueueName=self.test_sqs_queue_name)
        sqs_queue_url = sqs_queue_url_r['QueueUrl']
        sqs_resource = sqs_resource.Queue(url=sqs_queue_url)
        sqs_resource.delete()

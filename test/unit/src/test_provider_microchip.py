"""
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

Unit tests for provider_infineon

If run local with no local aws credentials, AWS_DEFAULT_REGION must be
set to the environment.
"""
import os
import json
from collections.abc import Iterator
from unittest import TestCase
from boto3 import resource, client
from moto import mock_aws
#from types_boto3_s3.service_resource import S3ServiceResource
from aws_lambda_powertools.utilities.data_classes import SQSEvent
from aws_lambda_powertools.utilities.typing import LambdaContext

from src.provider_microchip.provider_microchip.main import lambda_handler, invoke_export
from src.provider_microchip.provider_microchip.manifest_handler import get_iterator
from src.layer_utils.aws_utils import s3_object_bytes
from .model_provider_infineon import LambdaS3Class, LambdaSQSClass

@mock_aws(config={
    "core": {
        "mock_credentials": True,
        "reset_boto3_session": False,
        "service_whitelist": None,
    },
    'iot': {'use_valid_cert': True}})
class TestProviderInfineon(TestCase):
    """Infineon test cases"""
    def setUp(self):
        self.test_s3_bucket_name = "unit_test_s3_bucket"
        self.test_s3_object_content = None
        os.environ["S3_BUCKET_NAME"] = self.test_s3_bucket_name
        self.o_manifest_tlss_b = 'ECC608-TMNGTLSS-B.json'
        self.o_manifest_tlsu_b = 'ECC608C-TNGTLSU-B.json'
        f_manifest_tlss_b = './test/artifacts/' + self.o_manifest_tlss_b
        f_manifest_tlsu_b = './test/artifacts/' + self.o_manifest_tlsu_b
        self.o_validator = 'MCHP_manifest_signer_5_Mar_6-2024_noExpiration.crt'
        f_validator = './test/artifacts/mchp_verifiers/' + self.o_validator

        s3_client = client('s3', region_name="us-east-1")
        s3_client.create_bucket(Bucket = self.test_s3_bucket_name )

        with open(f_manifest_tlss_b, 'rb') as data:
            s3_client.put_object(Bucket=self.test_s3_bucket_name,
                                 Key=self.o_manifest_tlss_b, Body=data)
            self.test_s3_manifest_tlss_b = s3_client.get_object(Bucket=self.test_s3_bucket_name,
                                                         Key=self.o_manifest_tlss_b)['Body']
        with open(f_manifest_tlsu_b, 'rb') as data:
            s3_client.put_object(Bucket=self.test_s3_bucket_name,
                                 Key=self.o_manifest_tlsu_b, Body=data)
            self.test_s3_manifest_tlsu_b = s3_client.get_object(Bucket=self.test_s3_bucket_name,
                                                         Key=self.o_manifest_tlsu_b)['Body']

        with open(f_validator, 'rb') as data:
            s3_client.put_object(Bucket=self.test_s3_bucket_name,
                                 Key=self.o_validator, Body=data)
            self.test_s3_validator = s3_client.get_object(Bucket=self.test_s3_bucket_name,
                                                          Key=self.o_validator)['Body']
        mocked_s3_resource = resource("s3")
        mocked_s3_resource = { "resource" : resource('s3'),
                               "bucket_name" : self.test_s3_bucket_name }
        self.mocked_s3_class = LambdaS3Class(mocked_s3_resource)

        self.test_sqs_queue_name = "provider"
        sqs_client = client('sqs', region_name="us-east-1")
        sqs_client.create_queue(QueueName=self.test_sqs_queue_name)
        mocked_sqs_resource = resource("sqs")
        mocked_sqs_resource = { "resource" : resource('sqs'),
                                "queue_name" : self.test_sqs_queue_name }
        self.mocked_sqs_class = LambdaSQSClass(mocked_sqs_resource)

    def test_neg_invoke_export(self):
        os.environ['VERIFY_CERT'] = self.o_validator
        config = {
            'policy_arn': 'dev_policy',
            'bucket': self.test_s3_bucket_name,
            'key': self.o_manifest_tlss_b
        }
        invoke_export(config, self.test_sqs_queue_name)

    def test_pos_invoke_export(self):
        os.environ['VERIFY_CERT'] = self.o_validator
        config = {
            'policy_arn': 'dev_policy',
            'bucket': self.test_s3_bucket_name,
            'key': self.o_manifest_tlsu_b
        }
        invoke_export(config, self.test_sqs_queue_name)

    def test_iter(self):
        """ Ensure that the class can effectively return an iterator """
        o = s3_object_bytes(self.test_s3_bucket_name, self.o_manifest_tlsu_b, True)
        x = get_iterator(o)
        assert isinstance(x, Iterator) is True

    def test_pos_lambda_handler_1(self):
        """Invoke the main handler with one file"""
        os.environ['QUEUE_TARGET'] = self.test_sqs_queue_name
        os.environ['VERIFY_CERT'] = 'MCHP_manifest_signer_5_Mar_6-2024_noExpiration.crt'

        r1 = {
            'policy_arn': 'dev_policy',
            'bucket': self.test_s3_bucket_name,
            'key': self.o_manifest_tlsu_b
        }
        h = { "Records": [{
                        'eventSource': 'aws:sqs',
                        'body': json.dumps(r1)
                        }]
                       }
        e : SQSEvent = SQSEvent(h)
        c : LambdaContext = LambdaContext()

        v = lambda_handler(e, c)
        os.environ['QUEUE_TARGET']=""
        assert v == h

    def tearDown(self):
        s3_resource = resource("s3",region_name="us-east-1")
        s3_bucket = s3_resource.Bucket( self.test_s3_bucket_name )
        for key in s3_bucket.objects.all():
            key.delete()
        s3_bucket.delete()

        sqs_resource = resource("sqs", region_name="us-east-1")
        sqs_client = client("sqs", "us-east-1")
        sqs_queue_url_r = sqs_client.get_queue_url(QueueName=self.test_sqs_queue_name)
        sqs_queue_url = sqs_queue_url_r['QueueUrl']
        sqs_resource = sqs_resource.Queue(url=sqs_queue_url)
        sqs_resource.delete()

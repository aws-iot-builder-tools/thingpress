"""
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

Unit tests for provider_infineon
"""
import sys
import os
import io
from unittest import TestCase
import pytest

import botocore
from boto3 import resource, client
from moto import mock_aws
#from moto import mock_aws, settings
#from aws_lambda_powertools.utilities.validation import validate

#from unittest.mock import MagicMock, patch

from src.provider_infineon.testable import LambdaS3Class, LambdaSQSClass
from src.provider_infineon.main import s3_object_stream, s3_filebuf_bytes
#from src.provider_infineon.main import lambda_handler, invoke_export
#from src.provider_infineon.schemas import INPUT_SCHEMA

@mock_aws(config={
    "core": {
        "mock_credentials": True,
        "reset_boto3_session": False,
        "service_whitelist": None,
    },
    'iot': {'use_valid_cert': True}})
class TestProviderInfineon(TestCase):
    
    def setUp(self):
        self.test_s3_bucket_name = "unit_test_s3_bucket"
        self.test_s3_object_content = None
        os.environ["S3_BUCKET_NAME"] = self.test_s3_bucket_name
        s3_client = client('s3', region_name="us-east-1")
        s3_client.create_bucket(Bucket = self.test_s3_bucket_name )
        with open('./test/artifacts/manifest-espressif.csv', 'rb') as data:
            s3_client.put_object(Bucket=self.test_s3_bucket_name, Key="manifest.csv", Body=data)
            self.test_s3_object_content = s3_client.get_object(Bucket=self.test_s3_bucket_name, Key="manifest.csv")['Body']
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

    def test_pos_s3_object_resource(self):
        r = s3_object_stream("unit_test_s3_bucket", "manifest.csv")
        assert isinstance(r, io.BytesIO)

    def test_neg_s3_object_resource(self):
        with pytest.raises(botocore.exceptions.ClientError) as e:
            r = s3_object_stream("unit_test_s3_buckets", "manifest")
        assert str(e.value) == "An error occurred (NoSuchBucket) when calling the HeadObject operation: The specified bucket does not exist"

    def test_pos_s3_filebuf_bytes(self):
        # The bytes should equal to the object in the bucket
        v = s3_filebuf_bytes("unit_test_s3_bucket", "manifest.csv")
        assert v == self.test_s3_object_content.read()

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

"""
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

Utility lambda layer unit testing
"""
import os
import io
from unittest import TestCase
from unittest.mock import MagicMock, patch
import pytest
from moto import mock_aws, settings
from botocore.exceptions import ClientError
from boto3 import resource, client

from aws_utils import s3_object_stream, s3_filebuf_bytes
from .model_provider_espressif import LambdaS3Class

@mock_aws(config={
    "core": {
        "mock_credentials": True,
        "reset_boto3_session": False,
        "service_whitelist": None,
    },
    'iot': {'use_valid_cert': True}})
class TestProviderEspressif(TestCase):
    """Unit tests for the espressif provider module"""
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

    def test_pos_s3_object_resource(self):
        """Basic pos test case for object resource"""
        r = s3_object_stream("unit_test_s3_bucket", "manifest.csv")
        assert isinstance(r, io.BytesIO)

    def test_neg_s3_object_resource(self):
        """Basic neg test case for object resource"""
        with pytest.raises(ClientError) as e:
            # Although this returns a value, no need to define var for it
            s3_object_stream("unit_test_s3_buckets", "manifest")
        errstr = "An error occurred (NoSuchBucket) when calling the " \
                 "HeadObject operation: The specified bucket does not exist"
        assert str(e.value) == errstr

    def test_pos_s3_filebuf_bytes(self):
        """Basic pos test case for byte buffer handling"""
        # The bytes should equal to the object in the bucket
        v = s3_filebuf_bytes("unit_test_s3_bucket", "manifest.csv")
        assert v == self.test_s3_object_content.read()

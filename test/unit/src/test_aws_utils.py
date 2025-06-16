"""
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

Utility lambda layer unit testing
"""
import os
import io
import json
from unittest import TestCase
from unittest.mock import MagicMock, patch

from pytest import raises

from moto import mock_aws, settings
from botocore.exceptions import ClientError
from boto3 import resource, client

from aws_utils import s3_object, s3_object_bytes, verify_queue
from aws_utils import get_policy_arn, get_thing_group_arn, get_thing_type_arn
from .model_provider_espressif import LambdaS3Class

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
class TestAwsUtils(TestCase):
    """Unit tests for the aws_utils common function module"""
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
        r = s3_object("unit_test_s3_bucket", "manifest.csv")
        assert isinstance(r, io.BytesIO)

    def test_neg_s3_object_resource(self):
        """Basic neg test case for object resource"""
        with raises(ClientError) as e:
            # Although this returns a value, no need to define var for it
            s3_object("unit_test_s3_buckets", "manifest")
        errstr = "An error occurred (NoSuchBucket) when calling the " \
                 "HeadObject operation: The specified bucket does not exist"
        assert str(e.value) == errstr

    def test_pos_s3_filebuf_bytes(self):
        """Basic pos test case for byte buffer handling"""
        # The bytes should equal to the object in the bucket
        v = s3_object_bytes("unit_test_s3_bucket", "manifest.csv", getvalue=True)
        assert v == self.test_s3_object_content.read()

    def test_pos_get_policy_arn(self):
        """Positive test case to return policy arn"""
        iot_client = client('iot')
        n = "test_pos_get_policy"
        p = json.dumps(IOT_POLICY)
        r1 = iot_client.create_policy(policyName=n, policyDocument=p)
        r2 = get_policy_arn(n)
        assert r1['policyArn'] == r2

    def test_neg_get_policy_arn(self):
        """Negative test for getting get_policy_arn"""
        with raises(ClientError) as exc:
            get_policy_arn("bad_policy")
        err = exc.value.response['Error']
        assert err['Code'] == 'ResourceNotFoundException'

    def test_neg_get_policy_arn2(self):
        """Negative test for getting get_policy_arn"""
        assert get_policy_arn(None) is None

    def test_pos_get_thing_group_arn(self):
        """Positive test case to return thing group arn"""
        iot_client = client('iot')
        n = "test_pos_get_thing_group"
        r1 = iot_client.create_thing_group(thingGroupName=n)
        r2 = get_thing_group_arn(thing_group_name=n)
        assert r1['thingGroupArn'] == r2

    def test_neg_get_thing_group_arn(self):
        """Negative test for getting thing_group_arn"""
        with raises(ClientError) as exc:
            get_thing_group_arn("9"*64)
        err = exc.value.response['Error']
        assert err['Code'] == 'ResourceNotFoundException'

    def test_pos_get_thing_type_arn(self):
        """Positive test case to return thing type arn"""
        n = "test_pos_get_thing_type"
        iot_client = client('iot')
        r1 = iot_client.create_thing_type(thingTypeName=n)
        r2 = get_thing_type_arn(type_name=n)
        assert r1['thingTypeArn'] == r2

    def test_neg_get_thing_type_arn(self):
        """Negative test for getting thing_type_arn"""
        with raises(ClientError) as exc:
            get_thing_type_arn("9"*64)
        err = exc.value.response['Error']
        assert err['Code'] == 'ResourceNotFoundException'

    def test_neg_verify_queue(self):
        """Negative test for verify_queue"""
        with raises(ClientError) as exc:
            verify_queue("bogus_queue")
        err = exc.value.response['Error']
        assert err['Code'] == 'AWS.SimpleQueueService.NonExistentQueue'

    def tearDown(self):
        s3_resource = resource("s3",region_name="us-east-1")
        s3_bucket = s3_resource.Bucket( self.test_s3_bucket_name )
        for key in s3_bucket.objects.all():
            key.delete()
        s3_bucket.delete()

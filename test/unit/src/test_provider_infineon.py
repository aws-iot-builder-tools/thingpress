"""
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

Unit tests for provider_infineon

If run local with no local aws credentials, AWS_DEFAULT_REGION must be
set to the environment.
"""
import os
import io
import json
from unittest import TestCase
#from pytest import raises, xfail
import pytest
from botocore.exceptions import ClientError
from boto3 import _get_default_session
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.utilities.data_classes import SQSEvent
from moto import mock_aws
from py7zr import FileInfo
from pytest import raises
from src.layer_utils.layer_utils.aws_utils import s3_object_bytes
from src.provider_infineon.provider_infineon.main import lambda_handler
from src.provider_infineon.provider_infineon.manifest_handler import verify_certtype, select_certificate_set, verify_certificate_set, send_certificates
from .model_provider_infineon import LambdaS3Class, LambdaSQSClass

def cr_fileinfo(fn: str):
    """Mock out FileInfo objects which are a result of 7z parsing"""
    return FileInfo(fn, None, None, None, None, None, None)

@mock_aws(config={
    "core": {
        "mock_credentials": True,
        "reset_boto3_session": False,
        "service_whitelist": None,
    },
    'iot': {'use_valid_cert': True}})
class TestProviderInfineon(TestCase):
    """Infineon provider test cases"""
    def __init__(self, x):
        super().__init__(x)
        os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
        os.environ["AWS_REGION"] = "us-east-1"
        os.environ["AWS_ACCESS_KEY_ID"] = "testing"
        os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
        os.environ["AWS_SECURITY_TOKEN"] = "testing"
        os.environ["AWS_SESSION_TOKEN"] = "testing"
        self.session = _get_default_session()

    def setUp(self):

        self.artifact = "manifest-infineon.7z"
        self.artifact_local = "./test/artifacts/manifest-infineon.7z"
        self.test_s3_bucket_name = "unit_test_s3_bucket"
        self.test_s3_object_content = None
        os.environ["S3_BUCKET_NAME"] = self.test_s3_bucket_name
        s3_client = _get_default_session().client('s3', region_name="us-east-1")
        s3_client.create_bucket(Bucket = self.test_s3_bucket_name )
        with open(self.artifact_local, 'rb') as data:
            s3_client.put_object(Bucket=self.test_s3_bucket_name,
                                 Key=self.artifact,
                                 Body=data)
            self.test_s3_object_content = s3_client.get_object(Bucket=self.test_s3_bucket_name,
                                                               Key=self.artifact)['Body']
        mocked_s3_resource = _get_default_session().resource("s3")
        mocked_s3_resource = { "resource" : _get_default_session().resource('s3'),
                               "bucket_name" : self.test_s3_bucket_name }
        self.mocked_s3_class = LambdaS3Class(mocked_s3_resource)

        self.test_sqs_queue_name = "provider"
        sqs_client = _get_default_session().client('sqs', region_name="us-east-1")
        sqs_client.create_queue(QueueName=self.test_sqs_queue_name)
        mocked_sqs_resource = _get_default_session().resource("sqs")
        mocked_sqs_resource = { "resource" : mocked_sqs_resource,
                                "queue_name" : self.test_sqs_queue_name }
        self.mocked_sqs_class = LambdaSQSClass(mocked_sqs_resource)

    def test_verify_certtype(self):
        """Test the certificate type selection"""
        assert verify_certtype("E0E0") is True
        assert verify_certtype("E0E1") is True
        assert verify_certtype("E0E2") is True
        with raises(ValueError) as exc:
            verify_certtype("XXXX")


    def test_verify_certificate_set(self):
        l1 = [cr_fileinfo("xxx_E0E0_Certs.7z"),cr_fileinfo("xxx_E0E1_Certs.7z"),cr_fileinfo("xxx_E0E2_Certs.7z")]
        l2 = [cr_fileinfo("xxx_E0E0_Certs.7z")]
        l3 = []
        v1 = "E0E0"
        v2 = "E0E1"
        v3 = "E0E2"
        v4 = "Garbage"
        v5 = ""
        assert verify_certificate_set(l1, v1) == "xxx_E0E0_Certs.7z"
        assert verify_certificate_set(l1, v2) == "xxx_E0E1_Certs.7z"
        assert verify_certificate_set(l1, v3) == "xxx_E0E2_Certs.7z"
        assert verify_certificate_set(l2, v1) == "xxx_E0E0_Certs.7z"
        with raises(ValueError) as exc:
            verify_certificate_set(l2, v4)
        with raises(ValueError) as exc:
            verify_certificate_set(l2, v5)
        with raises(ValueError) as exc:
            verify_certificate_set(l2, v4)
        assert verify_certificate_set(l3, v1) is None
        with raises(ValueError) as exc:
            verify_certificate_set(l3, v4)
        with raises(ValueError) as exc:
            verify_certificate_set(l3, v5)

    def test_select_certificate_bundle(self):
        """ Test file selection of single bundle """
        x = select_certificate_set(io.BytesIO(self.test_s3_object_content.read()),
                               "E0E0")
        assert isinstance(x, io.BytesIO) is True

    @pytest.mark.xfail(raises=FileNotFoundError)
    def test_select_certificate_bundle_bad_bundle_name(self):
        """ Test file selection of single bundle """
        with raises(ValueError) as exc:
            select_certificate_set(io.BytesIO(self.test_s3_object_content.read()),
                                   "E0E5")

    def test_invoke_export(self):
        o = s3_object_bytes(self.test_s3_bucket_name, self.artifact, False, self.session)
        assert isinstance(o, io.BytesIO) is True
        x1 = select_certificate_set(o, "E0E0")
        config = {
            'bucket': self.test_s3_bucket_name,
            'key': self.artifact
        }
        send_certificates(x1, config, self.test_sqs_queue_name, self.session)

    def test_pos_lambda_handler_1(self):
        """Invoke the main handler with one file"""
        r1 = {
            'policy_arn': 'dev_policy',
            'bucket': self.test_s3_bucket_name,
            'key': self.artifact
        }

        e = { "Records": [{
                    'eventSource': 'aws:sqs',
                    'body': json.dumps(r1)
                }]
            }
        os.environ['QUEUE_TARGET']=self.test_sqs_queue_name
        os.environ['CERT_TYPE']="E0E0"

        v = lambda_handler(SQSEvent(e), LambdaContext())
        os.environ['QUEUE_TARGET']=""
        os.environ['CERT_TYPE']=""
        assert v == e


    def test_neg_lambda_handler_no_queue(self):
        """Invoke the main handler with one file"""
        r1 = {
            'policy_arn': 'dev_policy',
            'bucket': self.test_s3_bucket_name,
            'key': self.artifact
        }

        e = { "Records": [{
                    'eventSource': 'aws:sqs',
                    'body': json.dumps(r1)
                }]
            }
        os.environ['CERT_TYPE']="E0E0"

        with raises(ClientError) as exc:
            lambda_handler(SQSEvent(e), LambdaContext())
        assert exc.typename == 'QueueDoesNotExist'

    def test_neg_lambda_handler_no_cert_type(self):
        """Invoke the main handler with one file"""
        r1 = {
            'policy_arn': 'dev_policy',
            'bucket': self.test_s3_bucket_name,
            'key': self.artifact
        }

        e = { "Records": [{
                    'eventSource': 'aws:sqs',
                    'body': json.dumps(r1)
                }]
            }
        os.environ['QUEUE_TARGET']=self.test_sqs_queue_name

        with raises(ValueError) as exc:
            lambda_handler(SQSEvent(e), LambdaContext())
        assert exc.typename == 'ValueError'

    def tearDown(self):
        s3_resource = _get_default_session().resource("s3",region_name="us-east-1")
        s3_bucket = s3_resource.Bucket( self.test_s3_bucket_name )
        for key in s3_bucket.objects.all():
            key.delete()
        s3_bucket.delete()

        sqs_resource = _get_default_session().resource("sqs", region_name="us-east-1")
        sqs_client = _get_default_session().client("sqs", "us-east-1")
        sqs_queue_url_r = sqs_client.get_queue_url(QueueName=self.test_sqs_queue_name)
        sqs_queue_url = sqs_queue_url_r['QueueUrl']
        sqs_resource = sqs_resource.Queue(url=sqs_queue_url)
        sqs_resource.delete()
        os.environ['QUEUE_TARGET']=""
        os.environ['CERT_TYPE']=""

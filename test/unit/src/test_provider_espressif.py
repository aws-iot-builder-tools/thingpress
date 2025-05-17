import sys
import os
import io
import pytest
import warnings

import botocore
from boto3 import resource, client
from moto import mock_aws, settings
from aws_lambda_powertools.utilities.validation import validate

from unittest import TestCase
from unittest.mock import MagicMock, patch
sys.path.append('./src/provider_espressif')
from src.provider_espressif.main import LambdaS3Class, LambdaSQSClass   # pylint: disable=wrong-import-position
from src.provider_espressif.main import lambda_handler, s3_filebuf_bytes, invoke_export  # pylint: disable=wrong-import-position
from src.provider_espressif.main import s3_object_stream
from src.provider_espressif.main import INPUT_SCHEMA                     # pylint: disable=wrong-import-position

@mock_aws
class TestProviderEspressif(TestCase):
    
    def setUp(self):
        self.test_s3_bucket_name = "unit_test_s3_bucket"
        os.environ["S3_BUCKET_NAME"] = self.test_s3_bucket_name
        s3_client = client('s3', region_name="us-east-1")
        s3_client.create_bucket(Bucket = self.test_s3_bucket_name )
        with open('./test/artifacts/manifest-espressif.csv', 'rb') as data:
            s3_client.put_object(Bucket=self.test_s3_bucket_name, Key="manifest.csv", Body=data)
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
        s3_filebuf_bytes("unit_test_s3_bucket", "manifest.csv")

    def test_pos_invoke_export(self):
        invoke_export("unit_test_s3_bucket", "manifest.csv", "provider")
        # The number of items in the queue should be 1
        
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

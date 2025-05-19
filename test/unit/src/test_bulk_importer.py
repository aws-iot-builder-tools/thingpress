import sys
import os
import io
import pytest

import botocore

from boto3 import resource, client
from moto import mock_aws, settings
from moto.settings import iot_use_valid_cert

from aws_lambda_powertools.utilities.validation import validate

from unittest import TestCase
from unittest.mock import MagicMock, patch
sys.path.append('./src/bulk_importer')
os.environ['AWS_DEFAULT_REGION'] = "us-east-1"
from src.bulk_importer.testable import LambdaSQSClass   # pylint: disable=wrong-import-position
from src.bulk_importer.main import lambda_handler, get_certificate, get_certificate_fingerprint, get_certificate_arn, get_thing, get_policy, get_thing_group, get_thing_type, process_policy, process_thing, requeue, process_certificate, process_thing_group, get_name_from_certificate, process_sqs # pylint: disable=wrong-import-position
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
import base64

@mock_aws(config={'iot': {'use_valid_cert': True}})
class TestBulkImporter(TestCase):
    def setUp(self):
        self.test_sqs_queue_name = "provider"
        sqs_client = client('sqs', region_name="us-east-1")
        sqs_client.create_queue(QueueName=self.test_sqs_queue_name)
        mocked_sqs_resource = resource("sqs")
        mocked_sqs_resource = { "resource" : resource('sqs'),
                                "queue_name" : self.test_sqs_queue_name }
        self.mocked_sqs_class = LambdaSQSClass(mocked_sqs_resource)

    def test_pos_process_certificate(self):
        with open('./test/artifacts/single.pem', 'rb') as data:
            pem_obj = x509.load_pem_x509_certificate(data.read(),
                                                     backend=default_backend())
            block = pem_obj.public_bytes(encoding=serialization.Encoding.PEM).decode('ascii')
            cert = str(base64.b64encode(block.encode('ascii')))
            r = process_certificate(cert)
            assert (r == get_certificate_fingerprint(pem_obj))

    def tearDown(self):
        sqs_resource = resource("sqs", region_name="us-east-1")
        sqs_client = client("sqs", "us-east-1")
        sqs_queue_url_r = sqs_client.get_queue_url(QueueName=self.test_sqs_queue_name)
        sqs_queue_url = sqs_queue_url_r['QueueUrl']
        sqs_resource = sqs_resource.Queue(url=sqs_queue_url)
        sqs_resource.delete()

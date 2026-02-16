"""
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

Unit tests for MES Verifier
"""
import os
import json
from unittest import TestCase
from moto import mock_aws
from boto3 import resource, client, _get_default_session
from aws_lambda_powertools.utilities.data_classes import S3Event
from aws_lambda_powertools.utilities.typing import LambdaContext
from src.mes_verifier.main import lambda_handler
from src.layer_utils.layer_utils.circuit_state import reset_circuit

os.environ["AWS_DEFAULT_REGION"] = "us-east-1"


@mock_aws(config={
    "core": {
        "mock_credentials": True,
        "reset_boto3_session": False,
        "service_whitelist": None,
    },
    'iot': {'use_valid_cert': True}})
class TestMesVerifier(TestCase):
    """Test cases for MES Verifier lambda function"""

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
        self.bucket_mes = "thingpress-mes-stackname"
        self.obj_mes = "device-infos.json"
        self.queue_target_mes = "Thingpress-Mes-Provider-stackname"
        self.policy_name = "test-policy"
        self.thing_group_name = "test-group"
        self.thing_type_name = "test-type"

        # Create S3 bucket
        s3_client = client('s3', region_name='us-east-1')
        s3_client.create_bucket(Bucket=self.bucket_mes)

        # Upload test file
        test_data = {
            "batch_id": "test-batch",
            "devices": [
                {
                    "certFingerprint": "a" * 64,
                    "deviceId": "device-001",
                    "attributes": {"DSN": "DSN123"}
                }
            ]
        }
        s3_client.put_object(
            Bucket=self.bucket_mes,
            Key=self.obj_mes,
            Body=json.dumps(test_data).encode('utf-8')
        )

        # Create SQS queue
        sqs_client = client('sqs', region_name="us-east-1")
        sqs_client.create_queue(QueueName=self.queue_target_mes)

    def tearDown(self):
        # Clean up environment variables
        env_vars_to_clear = [
            'POLICY_NAMES', 'THING_GROUP_NAMES', 'THING_TYPE_NAME',
            'QUEUE_TARGET_MES'
        ]
        for var in env_vars_to_clear:
            os.environ.pop(var, None)

        # Clean up SQS queue
        sqs_resource = resource("sqs", region_name="us-east-1")
        sqs_client = client("sqs", "us-east-1")

        try:
            sqs_queue_url_r = sqs_client.get_queue_url(QueueName=self.queue_target_mes)
            sqs_queue_url = sqs_queue_url_r['QueueUrl']
            sqs_resource.Queue(url=sqs_queue_url).delete()
        except Exception:
            pass

        # Clean up S3 bucket
        s3_resource = resource('s3', region_name='us-east-1')
        try:
            bucket = s3_resource.Bucket(self.bucket_mes)
            bucket.objects.all().delete()
            bucket.delete()
        except Exception:
            pass

    # Simple policy document for testing
    IOT_POLICY = {
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Action": "iot:Connect",
            "Resource": "*"
        }]
    }

    def test_mes_verifier_basic(self):
        """Test basic MES verifier functionality"""
        reset_circuit('iot_get_policy')

        # Setup
        os.environ['POLICY_NAMES'] = self.policy_name
        os.environ['THING_GROUP_NAMES'] = 'None'
        os.environ['THING_TYPE_NAME'] = 'None'
        os.environ['QUEUE_TARGET_MES'] = self.queue_target_mes

        iot_client = self.session.client('iot')
        iot_client.create_policy(
            policyName=self.policy_name,
            policyDocument=json.dumps(self.IOT_POLICY)
        )

        # Create S3 event
        s3_event = {
            "Records": [{
                "eventSource": "aws:s3",
                "s3": {
                    "bucket": {"name": self.bucket_mes},
                    "object": {"key": self.obj_mes}
                }
            }]
        }

        # Execute
        result = lambda_handler(S3Event(s3_event), LambdaContext())

        # Verify
        self.assertEqual(result, s3_event)

        # Check message sent to SQS
        sqs_client = self.session.client("sqs")
        queue_url = sqs_client.get_queue_url(QueueName=self.queue_target_mes)['QueueUrl']
        messages = sqs_client.receive_message(QueueUrl=queue_url, MaxNumberOfMessages=10)

        self.assertIn('Messages', messages)
        self.assertEqual(len(messages['Messages']), 1)

        message_body = json.loads(messages['Messages'][0]['Body'])
        self.assertEqual(message_body['bucket'], self.bucket_mes)
        self.assertEqual(message_body['key'], self.obj_mes)
        self.assertIn('policies', message_body)

    def test_mes_verifier_hardcoded_config(self):
        """Test that MES verifier uses hardcoded FINGERPRINT configuration"""
        reset_circuit('iot_get_policy')

        # Setup
        os.environ['POLICY_NAMES'] = self.policy_name
        os.environ['THING_GROUP_NAMES'] = 'None'
        os.environ['THING_TYPE_NAME'] = 'None'
        os.environ['QUEUE_TARGET_MES'] = self.queue_target_mes

        iot_client = self.session.client('iot')
        iot_client.create_policy(
            policyName=self.policy_name,
            policyDocument=json.dumps(self.IOT_POLICY)
        )

        # Create S3 event
        s3_event = {
            "Records": [{
                "eventSource": "aws:s3",
                "s3": {
                    "bucket": {"name": self.bucket_mes},
                    "object": {"key": self.obj_mes}
                }
            }]
        }

        # Execute
        lambda_handler(S3Event(s3_event), LambdaContext())

        # Verify MES-specific hardcoded configuration
        sqs_client = self.session.client("sqs")
        queue_url = sqs_client.get_queue_url(QueueName=self.queue_target_mes)['QueueUrl']
        messages = sqs_client.receive_message(QueueUrl=queue_url, MaxNumberOfMessages=10)

        message_body = json.loads(messages['Messages'][0]['Body'])

        # MES Verifier should always use these hardcoded values
        self.assertEqual(message_body['cert_format'], 'FINGERPRINT')
        self.assertEqual(message_body['thing_deferred'], 'FALSE')
        self.assertEqual(message_body['cert_active'], 'TRUE')

    def test_mes_verifier_with_thing_groups(self):
        """Test MES verifier with multiple thing groups"""
        reset_circuit('iot_get_policy')
        reset_circuit('iot_get_thing_group')

        # Setup
        iot_client = self.session.client('iot')
        iot_client.create_policy(
            policyName=self.policy_name,
            policyDocument=json.dumps(self.IOT_POLICY)
        )
        iot_client.create_thing_group(thingGroupName='group-1')
        iot_client.create_thing_group(thingGroupName='group-2')

        os.environ['POLICY_NAMES'] = self.policy_name
        os.environ['THING_GROUP_NAMES'] = 'group-1,group-2'
        os.environ['THING_TYPE_NAME'] = 'None'
        os.environ['QUEUE_TARGET_MES'] = self.queue_target_mes

        # Create S3 event
        s3_event = {
            "Records": [{
                "eventSource": "aws:s3",
                "s3": {
                    "bucket": {"name": self.bucket_mes},
                    "object": {"key": self.obj_mes}
                }
            }]
        }

        # Execute
        lambda_handler(S3Event(s3_event), LambdaContext())

        # Verify thing groups in message
        sqs_client = self.session.client("sqs")
        queue_url = sqs_client.get_queue_url(QueueName=self.queue_target_mes)['QueueUrl']
        messages = sqs_client.receive_message(QueueUrl=queue_url, MaxNumberOfMessages=10)

        message_body = json.loads(messages['Messages'][0]['Body'])

        self.assertIn('thing_groups', message_body)
        self.assertEqual(len(message_body['thing_groups']), 2)
        group_names = [g['name'] for g in message_body['thing_groups']]
        self.assertIn('group-1', group_names)
        self.assertIn('group-2', group_names)

    def test_mes_verifier_with_thing_type(self):
        """Test MES verifier with thing type"""
        reset_circuit('iot_get_policy')
        reset_circuit('iot_get_thing_type')

        # Setup
        iot_client = self.session.client('iot')
        iot_client.create_policy(
            policyName=self.policy_name,
            policyDocument=json.dumps(self.IOT_POLICY)
        )
        iot_client.create_thing_type(thingTypeName=self.thing_type_name)

        os.environ['POLICY_NAMES'] = self.policy_name
        os.environ['THING_GROUP_NAMES'] = 'None'
        os.environ['THING_TYPE_NAME'] = self.thing_type_name
        os.environ['QUEUE_TARGET_MES'] = self.queue_target_mes

        # Create S3 event
        s3_event = {
            "Records": [{
                "eventSource": "aws:s3",
                "s3": {
                    "bucket": {"name": self.bucket_mes},
                    "object": {"key": self.obj_mes}
                }
            }]
        }

        # Execute
        lambda_handler(S3Event(s3_event), LambdaContext())

        # Verify thing type in message
        sqs_client = self.session.client("sqs")
        queue_url = sqs_client.get_queue_url(QueueName=self.queue_target_mes)['QueueUrl']
        messages = sqs_client.receive_message(QueueUrl=queue_url, MaxNumberOfMessages=10)

        message_body = json.loads(messages['Messages'][0]['Body'])

        self.assertEqual(message_body['thing_type_name'], self.thing_type_name)

    def test_parse_comma_delimited_list(self):
        """Test comma-delimited list parsing function"""
        # pylint: disable=import-outside-toplevel
        from src.mes_verifier.main import parse_comma_delimited_list

        # Multiple values
        result = parse_comma_delimited_list("policy1,policy2,policy3")
        assert result == ["policy1", "policy2", "policy3"]

        # Single value
        assert parse_comma_delimited_list("policy1") == ["policy1"]

        # None values
        assert parse_comma_delimited_list("None") == []
        assert parse_comma_delimited_list("none") == []
        assert parse_comma_delimited_list("") == []

        # Whitespace handling
        assert parse_comma_delimited_list("  policy1  ,  policy2  ") == ["policy1", "policy2"]

        # Mixed None
        assert parse_comma_delimited_list("policy1,None,policy2") == ["policy1", "policy2"]

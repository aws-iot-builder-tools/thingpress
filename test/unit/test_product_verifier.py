"""
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

Unit tests for bulk_importer
"""
import os
import json
from unittest import TestCase
from pytest import raises
from moto import mock_aws
from boto3 import resource, client, _get_default_session
from aws_lambda_powertools.utilities.data_classes import S3Event
from aws_lambda_powertools.utilities.typing import LambdaContext
from src.product_verifier.main import lambda_handler, get_provider_queue
from src.layer_utils.layer_utils.circuit_state import reset_circuit
from .model_product_verifier import LambdaS3Class, LambdaSQSClass

os.environ["AWS_DEFAULT_REGION"] = "us-east-1"

@mock_aws(config={
    "core": {
        "mock_credentials": True,
        "reset_boto3_session": False,
        "service_whitelist": None,
    },
    'iot': {'use_valid_cert': True}})
class TestProductProvider(TestCase):
    """Test cases for product provider lambda function"""
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
        self.obj_dir = "./test/artifacts/"
        self.obj_espressif = "manifest-espressif.csv"
        self.obj_infineon = "manifest-infineon.7z"
        self.obj_microchip = "ECC608C-TNGTLSU-B.json"
        self.obj_generated = "certificates_test.txt"
        self.bucket_espressif_pos = "thingpress-espressif-stackname"
        self.bucket_espressif_neg = "thingpress-espressi-stackname"
        self.bucket_infineon_pos = "thingpress-infineon-stackname"
        self.bucket_infineon_neg = "thingpress-infineo-stackname"
        self.bucket_microchip_pos = "thingpress-microchip-stackname"
        self.bucket_microchip_neg = "thingpress-microchi-stackname"
        self.bucket_generated_pos = "thingpress-generated-stackname"
        self.bucket_generated_neg = "thingpress-generate-stackname"

        self.obj_espressif_local = self.obj_dir + self.obj_espressif
        self.obj_infineon_local = self.obj_dir + self.obj_infineon
        self.obj_microchip_local = self.obj_dir + self.obj_microchip
        self.obj_generated_local = self.obj_dir + self.obj_generated

        # QUEUE_TARGET_ESPRESSIF
        self.env_queue_target_espressif = "Thingpress-Espressif-Provider-stackname"
        # QUEUE_TARGET_INFINEON
        self.env_queue_target_infineon = "Thingpress-Infineon-Provider-stackname"
        # QUEUE_TARGET_MICROCHIP
        self.env_queue_target_microchip = "Thingpress-Microchip-Provider-stackname"
        # QUEUE_TARGET_GENERATED
        self.env_queue_target_generated = "Thingpress-Generated-Provider-stackname"
        # env: POLICY_NAME
        self.env_policy_name_pos = "myPolicy"
        self.env_policy_name_neg = "myBadPolicy"
        # env: THING_GROUP_NAME
        self.env_thing_group_name_pos = "myThingGroup"
        self.env_thing_group_name_neg = "myBadThingGroup"
        # env: THING_TYPE_NAME
        self.env_thing_type_name_pos = "myThingType"
        self.env_thing_type_name_neg = "myBadThingType"

        s3_client = client('s3', region_name='us-east-1')

        s3_client.create_bucket(Bucket = self.bucket_espressif_pos )
        s3_client.create_bucket(Bucket = self.bucket_espressif_neg )
        s3_client.create_bucket(Bucket = self.bucket_infineon_pos )
        s3_client.create_bucket(Bucket = self.bucket_infineon_neg )
        s3_client.create_bucket(Bucket = self.bucket_microchip_pos )
        s3_client.create_bucket(Bucket = self.bucket_microchip_neg )
        s3_client.create_bucket(Bucket = self.bucket_generated_pos )
        s3_client.create_bucket(Bucket = self.bucket_generated_neg )

        self.mocked_s3_espressif_pos = LambdaS3Class({
            "resource" : resource('s3'),
            "bucket_name" : self.bucket_espressif_pos })

        with open(self.obj_espressif_local, 'rb') as data:
            s3_client.put_object(Bucket=self.bucket_espressif_pos,
                                 Key=self.obj_espressif,
                                 Body=data)



        sqs_client = client('sqs', region_name="us-east-1")
        sqs_client.create_queue(QueueName=self.env_queue_target_espressif)
        mocked_sqs_resource = resource("sqs")
        mocked_sqs_resource = { "resource" : resource('sqs'),
                                "queue_name" : self.env_queue_target_espressif }
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
    def test_gpq_generated_pos(self):
        os.environ['QUEUE_TARGET_GENERATED'] = self.env_queue_target_generated
        assert get_provider_queue(self.bucket_generated_pos) == self.env_queue_target_generated

    def test_gpq_espressif_neg(self):
        """ Tests espressif bucket pattern """
        os.environ['QUEUE_TARGET_ESPRESSIF'] = "Thingpress-Espressif-Provider-stackname"
        bucket = "thingpress-espressi-stackname"
        with raises(ValueError) as e:
            get_provider_queue(bucket)
        assert e.typename == 'ValueError'

    def test_gpq_infineon_neg(self):
        """ Tests infineon bucket pattern """
        os.environ['QUEUE_TARGET_INFINEON'] = "Thingpress-Infineon-Provider-stackname"
        bucket = "thingpress-infineo-stackname"
        with raises(ValueError) as e:
            get_provider_queue(bucket)
        assert e.typename == 'ValueError'

    def test_gpq_microchip_neg(self):
        """ Tests microchip bucket pattern """
        os.environ['QUEUE_TARGET_MICROCHIP'] = "Thingpress-Microchip-Provider-stackname"
        bucket = "thingpress-microchi-stackname"
        with raises(ValueError) as e:
            get_provider_queue(bucket)
        assert e.typename == 'ValueError'
        
    def test_gpq_generated_neg(self):
        """ Tests generated bucket pattern """
        os.environ['QUEUE_TARGET_GENERATED'] = "Thingpress-Generated-Provider-stackname"
        bucket = "thingpress-generate-stackname"
        with raises(ValueError) as e:
            get_provider_queue(bucket)
        assert e.typename == 'ValueError'

    def test_pos_invoke_export(self):
        """ The number of items in the queue should be 7 since there are
            seven certificates in the test file """

        os.environ['POLICY_NAMES'] = 'dev_policy'
        os.environ['THING_GROUP_NAMES'] = "None"
        os.environ['THING_TYPE_NAME'] = "None"
        os.environ['QUEUE_TARGET_ESPRESSIF'] = self.env_queue_target_espressif


        policy_document = {
	        "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "iot:Connect"
                    ],
                    "Resource": "arn:aws:iot:us-east-1:123456789012:client/client1",
                    "Condition": {
                        "ForAllValues:StringEquals": {
                            "iot:ConnectAttributes": [
                                "PersistentConnect",
                                "LastWill"
                            ]
                        }
                    }
                }
            ]
        }

        s3_event = {
            'Records': [
                {
                    'eventSource': 'aws:s3',
                    's3': {
                        'bucket': {
                            'name': self.bucket_espressif_pos,
                        },
                        'object': {
                            'key': self.obj_espressif,
                        }
                    }
                }
            ]
        }
        iotc = client('iot')
        iotc.create_policy(policyName='dev_policy',
                           policyDocument=json.dumps(policy_document))

        lambda_handler(S3Event(s3_event), LambdaContext())
        sqs_client = self.session.client("sqs")
        sqs_queue_url_r = sqs_client.get_queue_url(QueueName=self.env_queue_target_espressif)
        sqs_queue_url = sqs_queue_url_r['QueueUrl']
        p = sqs_client.get_queue_attributes(QueueUrl=sqs_queue_url,
                                            AttributeNames=['ApproximateNumberOfMessages'])
        assert p['Attributes']['ApproximateNumberOfMessages'] == '1'


    def test_neg_invoke_export(self):
        """ The number of items in the queue should be 7 since there are
            seven certificates in the test file """

        os.environ['POLICY_NAMES'] = 'dev_policy'
        os.environ['THING_GROUP_NAMES'] = "None"
        os.environ['THING_TYPE_NAME'] = "None"
        os.environ['QUEUE_TARGET_ESPRESSIF'] = self.env_queue_target_espressif
        reset_circuit('iot_get_policy')

        policy_document = {
	        "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "iot:Connect"
                    ],
                    "Resource": "arn:aws:iot:us-east-1:123456789012:client/client1",
                    "Condition": {
                        "ForAllValues:StringEquals": {
                            "iot:ConnectAttributes": [
                                "PersistentConnect",
                                "LastWill"
                            ]
                        }
                    }
                }
            ]
        }

        s3_event = {
            'Records': [
                {
                    'eventSource': 'aws:s3',
                    's3': {
                        'bucket': {
                            'name': self.bucket_espressif_neg,
                        },
                        'object': {
                            'key': self.obj_espressif,
                        }
                    }
                }
            ]
        }
        iotc = self.session.client('iot')
        iotc.create_policy( policyName='dev_policy', policyDocument=json.dumps(policy_document) )

        with raises(ValueError) as e:
            r = lambda_handler(S3Event(s3_event), LambdaContext())
            assert r == s3_event
        assert e.typename == 'ValueError'

    def tearDown(self):
        # Clean up environment variables to prevent test pollution
        env_vars_to_clear = [
            'POLICY_NAMES', 'THING_GROUP_NAMES', 'THING_TYPE_NAME',
            'QUEUE_TARGET_ESPRESSIF', 'QUEUE_TARGET_INFINEON',
            'QUEUE_TARGET_MICROCHIP', 'QUEUE_TARGET_GENERATED'
        ]
        for var in env_vars_to_clear:
            os.environ.pop(var, None)
        
        # Clean up SQS queues
        sqs_resource = resource("sqs", region_name="us-east-1")
        sqs_client = client("sqs", "us-east-1")
        
        # Clean up Espressif queue
        try:
            sqs_queue_url_r = sqs_client.get_queue_url(QueueName=self.env_queue_target_espressif)
            sqs_queue_url = sqs_queue_url_r['QueueUrl']
            sqs_resource.Queue(url=sqs_queue_url).delete()
        except Exception:
            pass
            
        # Clean up Generated queue
        try:
            sqs_queue_url_r = sqs_client.get_queue_url(QueueName=self.env_queue_target_generated)
            sqs_queue_url = sqs_queue_url_r['QueueUrl']
            sqs_resource.Queue(url=sqs_queue_url).delete()
        except Exception:
            pass
            
        # Clean up S3 buckets
        s3_resource = resource('s3', region_name='us-east-1')
        for bucket_name in [
            self.bucket_espressif_pos, self.bucket_espressif_neg,
            self.bucket_infineon_pos, self.bucket_infineon_neg,
            self.bucket_microchip_pos, self.bucket_microchip_neg,
            self.bucket_generated_pos, self.bucket_generated_neg
        ]:
            try:
                bucket = s3_resource.Bucket(bucket_name)
                bucket.objects.all().delete()
                bucket.delete()
            except Exception:
                pass
    def test_pos_lambda_handler_generated(self):
        """Test the lambda handler with a generated certificates file"""
        os.environ['POLICY_NAMES'] = self.env_policy_name_pos
        os.environ['THING_GROUP_NAMES'] = self.env_thing_group_name_pos
        os.environ['THING_TYPE_NAME'] = self.env_thing_type_name_pos
        os.environ['QUEUE_TARGET_GENERATED'] = self.env_queue_target_generated

        # Create IoT policy
        iot_client = client('iot', region_name='us-east-1')
        policy_document = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": "iot:*",
                    "Resource": "*"
                }
            ]
        }
        iot_client.create_policy(
            policyName=self.env_policy_name_pos,
            policyDocument=json.dumps(policy_document)
        )

        # Create IoT thing group
        iot_client.create_thing_group(
            thingGroupName=self.env_thing_group_name_pos
        )

        # Create IoT thing type
        iot_client.create_thing_type(
            thingTypeName=self.env_thing_type_name_pos
        )

        # Create SQS queue for generated provider
        sqs_client = client('sqs', region_name="us-east-1")
        sqs_client.create_queue(QueueName=self.env_queue_target_generated)

        # Upload test certificate file to S3
        s3_client = client('s3', region_name='us-east-1')
        with open(self.obj_generated_local, 'rb') as data:
            s3_client.put_object(
                Bucket=self.bucket_generated_pos,
                Key="certificates/" + self.obj_generated,
                Body=data
            )

        # Create S3 event
        s3_event = {
            "Records": [
                {
                    "eventVersion": "2.0",
                    "eventSource": "aws:s3",
                    "awsRegion": "us-east-1",
                    "eventTime": "2023-01-01T00:00:00.000Z",
                    "eventName": "ObjectCreated:Put",
                    "userIdentity": {
                        "principalId": "EXAMPLE"
                    },
                    "requestParameters": {
                        "sourceIPAddress": "127.0.0.1"
                    },
                    "responseElements": {
                        "x-amz-request-id": "EXAMPLE123456789",
                        "x-amz-id-2": "EXAMPLE123/abcdefghijklmno"
                    },
                    "s3": {
                        "s3SchemaVersion": "1.0",
                        "configurationId": "testConfigRule",
                        "bucket": {
                            "name": self.bucket_generated_pos,
                            "ownerIdentity": {
                                "principalId": "EXAMPLE"
                            },
                            "arn": f"arn:aws:s3:::{self.bucket_generated_pos}"
                        },
                        "object": {
                            "key": "certificates/" + self.obj_generated,
                            "size": 1024,
                            "eTag": "0123456789abcdef0123456789abcdef",
                            "sequencer": "0A1B2C3D4E5F678901"
                        }
                    }
                }
            ]
        }

        # Call lambda handler
        result = lambda_handler(S3Event(s3_event), LambdaContext())

        # Verify result
        self.assertEqual(result, s3_event)

        # Check that message was sent to SQS queue
        queue_url = sqs_client.get_queue_url(QueueName=self.env_queue_target_generated)['QueueUrl']
        messages = sqs_client.receive_message(
            QueueUrl=queue_url,
            MaxNumberOfMessages=10
        )

        # Verify that a message was sent to the queue
        self.assertIn('Messages', messages)
        self.assertEqual(len(messages['Messages']), 1)

        # Verify message content
        message_body = json.loads(messages['Messages'][0]['Body'])
        self.assertEqual(message_body['bucket'], self.bucket_generated_pos)
        self.assertEqual(message_body['key'], "certificates/" + self.obj_generated)
        # Check new multi-value format (even when using legacy env vars)
        self.assertIn('policies', message_body)
        self.assertEqual(len(message_body['policies']), 1)
        self.assertEqual(message_body['policies'][0]['name'], self.env_policy_name_pos)
        self.assertIn('thing_groups', message_body)
        self.assertEqual(len(message_body['thing_groups']), 1)
        self.assertEqual(message_body['thing_type_name'], self.env_thing_type_name_pos)


    # ========================================================================
    # v1.0.1 Tests - Multiple Policies and Thing Groups Support
    # ========================================================================
    
    # Simple policy document for testing
    IOT_POLICY = {
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Action": "iot:Connect",
            "Resource": "*"
        }]
    }

    def test_parse_comma_delimited_list(self):
        """Test comma-delimited list parsing function"""
        from src.product_verifier.main import parse_comma_delimited_list
        
        # Multiple values
        assert parse_comma_delimited_list("policy1,policy2,policy3") == ["policy1", "policy2", "policy3"]
        
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

    def test_lambda_handler_multiple_policies(self):
        """Test lambda handler with multiple policies"""
        reset_circuit('iot_get_policy')
        reset_circuit('iot_get_thing_group')
        
        # Setup
        iot_client = self.session.client('iot')
        sqs_client = self.session.client('sqs')
        s3_client = self.session.client('s3')
        
        # Create multiple policies
        iot_client.create_policy(policyName='test-policy-1', policyDocument=json.dumps(self.IOT_POLICY))
        iot_client.create_policy(policyName='test-policy-2', policyDocument=json.dumps(self.IOT_POLICY))
        
        # Set environment variables for multiple policies
        os.environ['POLICY_NAMES'] = 'test-policy-1,test-policy-2'
        os.environ['THING_GROUP_NAMES'] = 'None'
        os.environ['THING_TYPE_NAME'] = 'None'
        os.environ['QUEUE_TARGET_GENERATED'] = self.env_queue_target_generated
        
        # Create S3 bucket and upload object
        s3_client.create_bucket(Bucket=self.bucket_generated_pos)
        s3_client.put_object(Bucket=self.bucket_generated_pos, Key=self.obj_generated, Body=b'test')
        
        # Create SQS queue
        sqs_client.create_queue(QueueName=self.env_queue_target_generated)
        
        # Create S3 event
        s3_event = {
            "Records": [{
                "eventSource": "aws:s3",
                "s3": {
                    "bucket": {"name": self.bucket_generated_pos},
                    "object": {"key": self.obj_generated}
                }
            }]
        }
        
        # Execute
        result = lambda_handler(S3Event(s3_event), LambdaContext())
        
        # Verify message sent to SQS
        queue_url = sqs_client.get_queue_url(QueueName=self.env_queue_target_generated)['QueueUrl']
        messages = sqs_client.receive_message(QueueUrl=queue_url, MaxNumberOfMessages=10)
        
        self.assertIn('Messages', messages)
        message_body = json.loads(messages['Messages'][0]['Body'])
        
        # Verify policies list in message
        self.assertIn('policies', message_body)
        self.assertEqual(len(message_body['policies']), 2)
        policy_names = [p['name'] for p in message_body['policies']]
        self.assertIn('test-policy-1', policy_names)
        self.assertIn('test-policy-2', policy_names)

    def test_lambda_handler_multiple_thing_groups(self):
        """Test lambda handler with multiple thing groups"""
        reset_circuit('iot_get_policy')
        reset_circuit('iot_get_thing_group')
        
        # Setup
        iot_client = self.session.client('iot')
        sqs_client = self.session.client('sqs')
        s3_client = self.session.client('s3')
        
        # Create multiple thing groups
        iot_client.create_thing_group(thingGroupName='test-group-1')
        iot_client.create_thing_group(thingGroupName='test-group-2')
        
        # Set environment variables
        os.environ['POLICY_NAMES'] = 'None'
        os.environ['THING_GROUP_NAMES'] = 'test-group-1,test-group-2'
        os.environ['THING_TYPE_NAME'] = 'None'
        os.environ['QUEUE_TARGET_GENERATED'] = self.env_queue_target_generated
        
        # Create S3 bucket and upload object
        s3_client.create_bucket(Bucket=self.bucket_generated_pos)
        s3_client.put_object(Bucket=self.bucket_generated_pos, Key=self.obj_generated, Body=b'test')
        
        # Create SQS queue
        sqs_client.create_queue(QueueName=self.env_queue_target_generated)
        
        # Create S3 event
        s3_event = {
            "Records": [{
                "eventSource": "aws:s3",
                "s3": {
                    "bucket": {"name": self.bucket_generated_pos},
                    "object": {"key": self.obj_generated}
                }
            }]
        }
        
        # Execute
        result = lambda_handler(S3Event(s3_event), LambdaContext())
        
        # Verify message sent to SQS
        queue_url = sqs_client.get_queue_url(QueueName=self.env_queue_target_generated)['QueueUrl']
        messages = sqs_client.receive_message(QueueUrl=queue_url, MaxNumberOfMessages=10)
        
        self.assertIn('Messages', messages)
        message_body = json.loads(messages['Messages'][0]['Body'])
        
        # Verify thing_groups list in message
        self.assertIn('thing_groups', message_body)
        self.assertEqual(len(message_body['thing_groups']), 2)
        group_names = [g['name'] for g in message_body['thing_groups']]
        self.assertIn('test-group-1', group_names)
        self.assertIn('test-group-2', group_names)

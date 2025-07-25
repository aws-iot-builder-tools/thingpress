"""
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

Utility lambda layer unit testing
"""
import os
import io
import json
import base64
from unittest import TestCase
from unittest.mock import MagicMock, patch
from pytest import raises
from moto import mock_aws
from botocore.exceptions import ClientError
from boto3 import resource, client
from boto3 import Session, _get_default_session
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from src.layer_utils.layer_utils.aws_utils import s3_object, s3_object_bytes, verify_queue
from src.layer_utils.layer_utils.aws_utils import get_policy_arn, get_thing_group_arn, get_thing_type_arn, get_thing_arn
from src.layer_utils.layer_utils.aws_utils import send_sqs_message, send_sqs_message_batch, send_sqs_message_batch_with_retry
from src.layer_utils.layer_utils.aws_utils import get_queue_depth, calculate_optimal_delay, send_sqs_message_with_throttling, send_sqs_message_with_adaptive_throttling
from src.layer_utils.layer_utils.aws_utils import get_certificate_arn, register_certificate
from src.layer_utils.layer_utils.aws_utils import process_thing, process_thing_type, process_policy
from src.layer_utils.layer_utils.aws_utils import process_thing_group, boto_errorcode
from src.layer_utils.layer_utils.cert_utils import decode_certificate
from src.layer_utils.layer_utils.circuit_state import clear_circuits, reset_circuit

from .model_provider_espressif import LambdaS3Class

# Ensure that we are not using real AWS credentials
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
os.environ["AWS_REGION"] = "us-east-1"
os.environ["AWS_ACCESS_KEY_ID"] = "testing"
os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
os.environ["AWS_SECURITY_TOKEN"] = "testing"
os.environ["AWS_SESSION_TOKEN"] = "testing"

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
        clear_circuits()
        self.aws_session = _get_default_session()
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

        self.queue_url = _get_default_session().client('sqs').create_queue(QueueName='test-queue')['QueueUrl']
        iot_client = _get_default_session().client('iot')
        self.thing_group_arn_solo = (iot_client.create_thing_group(thingGroupName="Thing-Group-Solo"))['thingGroupArn']
        self.thing_group_arn_parent = (iot_client.create_thing_group(thingGroupName="Thing-Group-Parent"))['thingGroupArn']
        self.thing_group_arn_child = (iot_client.create_thing_group(thingGroupName="Thing-Group-Child",
                                                                    parentGroupName="Thing-Group-Parent"))['thingGroupArn']
        self.thing_type_name = "Thingpress-Thing-Type"
        self.thing_type_arn = (iot_client.create_thing_type(thingTypeName=self.thing_type_name))['thingTypeArn']

        # Format this as if it just came out of the queue
        with open('./test/artifacts/single.pem', 'rb') as data:
            pem_obj = x509.load_pem_x509_certificate(data.read(),
                                                     backend=default_backend())
            block = pem_obj.public_bytes(encoding=serialization.Encoding.PEM).decode('ascii')
            self.local_cert_loaded = str(base64.b64encode(block.encode('ascii')))

    def test_pos_s3_object_resource(self):
        """Basic pos test case for object resource"""
        r = s3_object("unit_test_s3_bucket", "manifest.csv", session=_get_default_session())
        assert isinstance(r, io.BytesIO)

    def test_neg_s3_object_resource(self):
        """Basic neg test case for object resource"""
        with raises(ClientError) as e:
            # Although this returns a value, no need to define var for it
            s3_object("unit_test_s3_buckets", "manifest", session=_get_default_session())
        errstr = "An error occurred (NoSuchBucket) when calling the " \
                 "HeadObject operation: The specified bucket does not exist"
        assert str(e.value) == errstr

    def test_pos_s3_filebuf_bytes(self):
        """Basic pos test case for byte buffer handling"""
        # The bytes should equal to the object in the bucket
        v = s3_object_bytes("unit_test_s3_bucket", "manifest.csv", getvalue=True, session=_get_default_session())
        assert v == self.test_s3_object_content.read()

    def test_pos_get_policy_arn(self):
        """Positive test case to return policy arn"""
        # Skip this test for now as it's failing due to circuit breaker issues
        # pytest.skip("Skipping due to circuit breaker issues")
        iot_client = _get_default_session().client('iot')
        n = "test_pos_get_policy"
        p = json.dumps(IOT_POLICY)
        clear_circuits()
        r1 = iot_client.create_policy(policyName=n, policyDocument=p)
        r2 = get_policy_arn(n, _get_default_session())
        assert r1['policyArn'] == r2

    def test_neg_get_policy_arn(self):
        """Negative test for getting get_policy_arn"""
        # Skip this test for now as it's failing due to circuit breaker issues
        # pytest.skip("Skipping due to circuit breaker issues")

        with raises(ClientError) as exc:
            get_policy_arn("bad_policy",  _get_default_session())
        if 'Error' in exc.value.response:
            err = exc.value.response['Error']
            if 'Code' in err:
                assert err['Code'] == 'ResourceNotFoundException'
            else:
                # force failure
                assert True is False

    def test_neg_get_policy_arn2(self):
        """Negative test for getting get_policy_arn"""
        clear_circuits()
        with raises(ValueError) as exc:
            get_policy_arn("None", _get_default_session())

        assert exc.typename == "ValueError"

    def test_pos_process_policy(self):
        """Positive test case for attaching policy to certificate"""
        iot_client = _get_default_session().client('iot')
        policy_name = "process_policy"
        policy_document = json.dumps(IOT_POLICY)
        iot_client.create_policy(policyName=policy_name, policyDocument=policy_document)

        cert = decode_certificate(self.local_cert_loaded).decode('ascii')
        certificate_id = register_certificate(cert, _get_default_session())
        certificate_arn = get_certificate_arn(certificate_id, _get_default_session())

        process_policy(policy_name, certificate_arn, _get_default_session())

    def test_pos_process_thing_group(self):
        iot_client = _get_default_session().client('iot')
        thing_group_arn = self.thing_group_arn_child
        thing_arn = iot_client.create_thing(thingName="test_pos_process_thing_group")['thingArn']
        process_thing_group(thing_group_arn, thing_arn, _get_default_session())

    def test_pos_get_thing_group_arn(self):
        """Positive test case to return thing group arn"""
        clear_circuits()

        with patch('boto3.Session.client') as mock_client:
            mock_iot = MagicMock()
            mock_iot.describe_thing_group.return_value = {
                'thingGroupArn': 'arn:aws:iot:us-east-1:123456789012:thinggroup/test_pos_get_thing_group'
            }
            mock_client.return_value = mock_iot
            
            iot_client = _get_default_session().client('iot')
            thing_group_name = "test_pos_get_thing_group"
            r1 = iot_client.create_thing_group(thingGroupName=thing_group_name)
            r2 = get_thing_group_arn(thing_group_name, _get_default_session())

            # Use the mock return value for comparison
            assert r2 == 'arn:aws:iot:us-east-1:123456789012:thinggroup/test_pos_get_thing_group'

    def test_neg_get_thing_group_arn(self):
        """Negative test for getting thing_group_arn"""
        clear_circuits()

        with patch('boto3.Session.client') as mock_client:
            mock_iot = MagicMock()
            mock_error_response = {
                'Error': {
                    'Code': 'ResourceNotFoundException',
                    'Message': 'Thing group not found'
                }
            }

            mock_iot.describe_thing_group.side_effect = ClientError(
                mock_error_response, 'DescribeThingGroup')
            mock_client.return_value = mock_iot

            with raises(ClientError) as exc:
                get_thing_group_arn("9"*64)

            if 'Error' in exc.value.response:
                err = exc.value.response['Error']
                if 'Code' in err:
                    assert err['Code'] == 'ResourceNotFoundException'
                else:
                    assert False # Could not find Code
            else:
                assert False # Could not find Error

    def test_pos_get_thing_type_arn(self):
        """Positive test case to return thing type arn"""
        type_name = "test_pos_get_thing_type"
        iot_client = _get_default_session().client('iot')
        r1 = iot_client.create_thing_type(thingTypeName=type_name)
        r2 = get_thing_type_arn(type_name, Session())
        assert r1['thingTypeArn'] == r2

    def test_neg_get_thing_type_arn(self):
        """Negative test for getting thing_type_arn"""
        with raises(ClientError) as exc:
            get_thing_type_arn("9"*64, self.aws_session)
        if 'Error' in exc.value.response:
            err = exc.value.response['Error']
            if 'Code' in err:
                assert err['Code'] == 'ResourceNotFoundException'
            else:
                assert False
        else:
            assert False

    def test_pos_get_thing_arn(self):
        """Positive test case to return thing arn"""
        thing_name = "test_pos_get_thing_arn"
        iot_client = _get_default_session().client('iot')
        r1 = iot_client.create_thing(thingName=thing_name)
        r2 = get_thing_arn(thing_name, _get_default_session())
        assert r1['thingArn'] == r2

    def test_neg_get_thing_arn(self):
        """Negative test for getting thing_arn"""
        with raises(ClientError) as exc:
            get_thing_arn("9"*64, self.aws_session)
        if 'Error' in exc.value.response:
            err = exc.value.response['Error']
            if 'Code' in err:
                assert err['Code'] == 'ResourceNotFoundException'
            else:
                assert False
        else:
            assert False

    def test_neg_get_thing_arn_none_value(self):
        """Negative test for getting thing_arn with None value"""
        with raises(ValueError) as exc:
            get_thing_arn("None", _get_default_session())
        assert "no thing defined" in str(exc.value)

        with raises(ValueError) as exc:
            get_thing_arn("", _get_default_session())
        assert "no thing defined" in str(exc.value)

    def test_neg_verify_queue(self):
        """Negative test for verify_queue"""
        clear_circuits()

        with patch('boto3.Session.client') as mock_client:
            mock_sqs = MagicMock()
            mock_error_response = {
                'Error': {
                    'Code': 'AWS.SimpleQueueService.NonExistentQueue',
                    'Message': 'The specified queue does not exist'
                }
            }
            mock_sqs.get_queue_attributes.side_effect = ClientError(
                mock_error_response, 'GetQueueAttributes')
            mock_client.return_value = mock_sqs

            with raises(ClientError) as exc:
                verify_queue("bogus_queue")
            if 'Error' in exc.value.response:
                err = exc.value.response['Error']
                if 'Code' in err:
                    assert err['Code'] == 'AWS.SimpleQueueService.NonExistentQueue'
                else:
                    assert False
            else:
                assert False

    def tearDown(self):
        clear_circuits()

        s3_resource = resource("s3",region_name="us-east-1")
        s3_bucket = s3_resource.Bucket( self.test_s3_bucket_name )
        for key in s3_bucket.objects.all():
            key.delete()
        s3_bucket.delete()
        _get_default_session().client('sqs').delete_queue(QueueUrl=self.queue_url)

    def test_circuit_breaker_reset(self):
        """Test that circuit breaker resets after successful call"""

        # First set up a failing circuit
        with patch('boto3.Session.client') as mock_client:
            # Configure the mock to raise ClientError
            mock_iot = MagicMock()
            mock_error_response = {
                'Error': {
                    'Code': 'ThrottlingException',
                    'Message': 'Rate exceeded'
                }
            }

            mock_iot.get_policy.side_effect = ClientError(
                mock_error_response, 'GetPolicy')
            mock_client.return_value = mock_iot

            # Call enough times to open the circuit
            for _ in range(5):
                with raises(ClientError):
                    get_policy_arn("test_policy")
            mock_iot.get_policy.side_effect = None

        # Now make the call succeed and verify circuit resets
        # We need to patch the client again to return success
        with patch('boto3.Session.client') as mock_client:
            mock_iot = MagicMock()
            mock_iot.get_policy.return_value = {'policyArn': 'arn:aws:iot:us-east-1:123456789012:policy/test_policy'}
            mock_client.return_value = mock_iot

            # Reset the circuit
            reset_circuit('iot_get_policy')

            # This should succeed and reset the circuit
            result = get_policy_arn("test_policy")
            assert result == 'arn:aws:iot:us-east-1:123456789012:policy/test_policy'

    def test_pos_send_sqs_message(self):
        """Test sending a message to SQS"""
        # Send a message
        message = {"key": "value"}
        with patch('boto3.Session.client') as mock_client:
            mock_sqs = MagicMock()
            mock_sqs.send_message.return_value = {'MessageId': '12345'}
            mock_client.return_value = mock_sqs

            result = send_sqs_message(message, self.queue_url, _get_default_session())

            # Verify message was sent
            assert result['MessageId'] == '12345'
            mock_sqs.send_message.assert_called_once()

    def test_pos_get_certificate_arn(self):
        """Positive test for get_certificate_arn"""
        cert = decode_certificate(self.local_cert_loaded).decode('ascii')
        certificate_id = register_certificate(cert, _get_default_session())
        certificate_arn = get_certificate_arn(certificate_id, _get_default_session())
        assert certificate_arn is not None

    def test_neg_get_certificate_arn(self):
        """Negative test for get_certificate_arn"""

        with raises(ClientError) as exc:
            get_certificate_arn("9"*64, _get_default_session())

        if 'Error' in exc.value.response:
            err = exc.value.response['Error']
            if 'Code' in err:
                assert err['Code'] == 'ResourceNotFoundException'
        else:
            assert False

    def test_pos_process_thing(self):
        """Positive test case for attaching policy to certificate"""
        iot_client = _get_default_session().client('iot')
        cert = decode_certificate(self.local_cert_loaded).decode('ascii')
        certificate_id = register_certificate(cert, _get_default_session())
        thing_name = "process_thing"
        iot_client.create_thing(thingName=thing_name)

        # Assume operation success with no raise
        process_thing(thing_name, certificate_id, session=_get_default_session())

    def test_pos_process_thing_with_type(self):
        """ Positive test case for attaching policy to certificate """
        iot_client = _get_default_session().client('iot')
        thing_name = "process_thing"
        iot_client.create_thing(thingName=thing_name)

        # Assume operation success with no raise
        process_thing_type(thing_name, self.thing_type_name, _get_default_session())

    def test_pos_process_thing_no_prev_thing(self):
        """Positive test case for attaching policy to certificate"""
        cert = decode_certificate(self.local_cert_loaded).decode('ascii')
        cr = register_certificate(cert, _get_default_session())

        # Assume operation success with no raise
        process_thing('my_thing', cr, session=_get_default_session())

    def test_pos_process_thing_with_type_no_prev_thing(self):
        """Positive test case for attaching policy to certificate"""
        cert = decode_certificate(self.local_cert_loaded).decode('ascii')
        cr = register_certificate(cert, _get_default_session())

        # Assume operation success with no raise
        process_thing('my_thing', cr, session=_get_default_session())

        # Assume operation success with no raise
        process_thing_type('my_thing', self.thing_type_name, _get_default_session())

    def test_neg_send_sqs_message_client_error(self):
        """Test handling of ClientError in send_sqs_message function"""
        message = {"key": "value"}
        
        with patch('boto3.Session.client') as mock_client:
            mock_sqs = MagicMock()
            mock_error_response = {
                'Error': {
                    'Code': 'InvalidParameterValue',
                    'Message': 'The request was rejected. The queue URL is invalid.'
                }
            }
            mock_sqs.send_message.side_effect = ClientError(
                mock_error_response, 'SendMessage')
            mock_client.return_value = mock_sqs

            with raises(ClientError) as exc:
                send_sqs_message(message, "invalid-queue-url", _get_default_session())
                
            assert boto_errorcode(exc.value) == 'InvalidParameterValue'
            mock_sqs.send_message.assert_called_once()

    def test_pos_send_sqs_message_batch(self):
        """Test sending multiple messages to SQS in batch"""
        messages = [
            {"thing": "device-001", "certificate": "cert1"},
            {"thing": "device-002", "certificate": "cert2"},
            {"thing": "device-003", "certificate": "cert3"}
        ]
        
        with patch('boto3.Session.client') as mock_client:
            mock_sqs = MagicMock()
            mock_sqs.send_message_batch.return_value = {
                'Successful': [
                    {'Id': '0', 'MessageId': 'msg-001'},
                    {'Id': '1', 'MessageId': 'msg-002'},
                    {'Id': '2', 'MessageId': 'msg-003'}
                ],
                'Failed': []
            }
            mock_client.return_value = mock_sqs

            result = send_sqs_message_batch(messages, self.queue_url, _get_default_session())

            # Verify batch was sent
            assert len(result) == 1
            assert len(result[0]['Successful']) == 3
            mock_sqs.send_message_batch.assert_called_once()
            
            # Verify batch entries were formatted correctly
            call_args = mock_sqs.send_message_batch.call_args
            entries = call_args[1]['Entries']
            assert len(entries) == 3
            assert entries[0]['Id'] == '0'
            assert 'device-001' in entries[0]['MessageBody']

    def test_pos_send_sqs_message_batch_large(self):
        """Test sending more than 10 messages (multiple batches)"""
        messages = [{"thing": f"device-{i:03d}", "certificate": f"cert{i}"} for i in range(25)]
        
        with patch('boto3.Session.client') as mock_client:
            mock_sqs = MagicMock()
            mock_sqs.send_message_batch.return_value = {
                'Successful': [{'Id': str(i), 'MessageId': f'msg-{i:03d}'} for i in range(10)],
                'Failed': []
            }
            mock_client.return_value = mock_sqs

            result = send_sqs_message_batch(messages, self.queue_url, _get_default_session())

            # Should make 3 batch calls (10 + 10 + 5)
            assert len(result) == 3
            assert mock_sqs.send_message_batch.call_count == 3

    def test_pos_send_sqs_message_batch_partial_failure(self):
        """Test handling partial failures in batch send"""
        messages = [
            {"thing": "device-001", "certificate": "cert1"},
            {"thing": "device-002", "certificate": "cert2"},
            {"thing": "device-003", "certificate": "cert3"}
        ]
        
        with patch('boto3.Session.client') as mock_client:
            mock_sqs = MagicMock()
            mock_sqs.send_message_batch.return_value = {
                'Successful': [
                    {'Id': '0', 'MessageId': 'msg-001'},
                    {'Id': '2', 'MessageId': 'msg-003'}
                ],
                'Failed': [
                    {'Id': '1', 'Code': 'InvalidParameterValue', 'Message': 'Invalid message'}
                ]
            }
            mock_client.return_value = mock_sqs

            result = send_sqs_message_batch(messages, self.queue_url, _get_default_session())

            # Should still return result with partial success
            assert len(result) == 1
            assert len(result[0]['Successful']) == 2
            assert len(result[0]['Failed']) == 1

    def test_pos_send_sqs_message_batch_with_retry(self):
        """Test batch send with retry functionality"""
        messages = [
            {"thing": "device-001", "certificate": "cert1"},
            {"thing": "device-002", "certificate": "cert2"}
        ]
        
        with patch('boto3.Session.client') as mock_client:
            mock_sqs = MagicMock()
            # First call fails partially, second call succeeds
            mock_sqs.send_message_batch.side_effect = [
                {
                    'Successful': [{'Id': '0', 'MessageId': 'msg-001'}],
                    'Failed': [{'Id': '1', 'Code': 'Throttling', 'Message': 'Rate exceeded'}]
                },
                {
                    'Successful': [{'Id': '0', 'MessageId': 'msg-002'}],
                    'Failed': []
                }
            ]
            mock_client.return_value = mock_sqs

            with patch('time.sleep'):  # Mock sleep to speed up test
                result = send_sqs_message_batch_with_retry(messages, self.queue_url, _get_default_session())

            # Should make 2 calls (initial + retry)
            assert mock_sqs.send_message_batch.call_count == 2
            assert len(result) == 2

    def test_neg_send_sqs_message_batch_client_error(self):
        """Test handling of ClientError in send_sqs_message_batch function"""
        messages = [{"thing": "device-001", "certificate": "cert1"}]
        
        with patch('boto3.Session.client') as mock_client:
            mock_sqs = MagicMock()
            mock_sqs.send_message_batch.side_effect = ClientError(
                error_response={'Error': {'Code': 'InvalidParameterValue', 'Message': 'Invalid queue URL'}},
                operation_name='SendMessageBatch'
            )
            mock_client.return_value = mock_sqs

            with raises(ClientError) as exc:
                send_sqs_message_batch(messages, "invalid-queue-url", _get_default_session())
                
            assert boto_errorcode(exc.value) == 'InvalidParameterValue'
            mock_sqs.send_message_batch.assert_called_once()

    def test_neg_send_sqs_message_batch_with_retry_max_retries(self):
        """Test batch send with retry when max retries exceeded"""
        messages = [{"thing": "device-001", "certificate": "cert1"}]
        
        with patch('boto3.Session.client') as mock_client:
            mock_sqs = MagicMock()
            mock_sqs.send_message_batch.side_effect = ClientError(
                error_response={'Error': {'Code': 'ServiceUnavailable', 'Message': 'Service unavailable'}},
                operation_name='SendMessageBatch'
            )
            mock_client.return_value = mock_sqs

            with patch('time.sleep'):  # Mock sleep to speed up test
                with raises(ClientError) as exc:
                    send_sqs_message_batch_with_retry(messages, self.queue_url, _get_default_session(), max_retries=2)
                
            assert boto_errorcode(exc.value) == 'ServiceUnavailable'
            assert mock_sqs.send_message_batch.call_count == 2  # Initial + 1 retry

    def test_pos_get_queue_depth(self):
        """Test getting queue depth metrics for throttling"""
        with patch('boto3.Session.client') as mock_client:
            mock_sqs = MagicMock()
            mock_sqs.get_queue_attributes.return_value = {
                'Attributes': {
                    'ApproximateNumberOfMessages': '150',
                    'ApproximateNumberOfMessagesNotVisible': '50',
                    'ApproximateNumberOfMessagesDelayed': '25'
                }
            }
            mock_client.return_value = mock_sqs

            result = get_queue_depth(self.queue_url, _get_default_session())

            assert result['visible'] == 150
            assert result['in_flight'] == 50
            assert result['delayed'] == 25
            assert result['total'] == 200
            assert result['queue_url'] == self.queue_url
            mock_sqs.get_queue_attributes.assert_called_once()

    def test_pos_calculate_optimal_delay(self):
        """Test calculating optimal delay based on queue depth"""
        # Test different queue depths
        assert calculate_optimal_delay(50) == 0      # Low load - no delay
        assert calculate_optimal_delay(200) == 15    # Low-medium load - half base delay
        assert calculate_optimal_delay(750) == 30    # Medium load - base delay
        assert calculate_optimal_delay(1500) == 60   # High load - double base delay
        assert calculate_optimal_delay(2500) == 120  # Very high load - 4x base delay
        
        # Test with custom base delay
        assert calculate_optimal_delay(750, base_delay=60) == 60
        assert calculate_optimal_delay(1500, base_delay=60) == 120

    def test_pos_send_sqs_message_with_throttling(self):
        """Test sending messages with throttling enabled"""
        messages = [{"thing": "device-001", "certificate": "cert1"}]
        
        with patch('boto3.Session.client') as mock_client:
            mock_sqs = MagicMock()
            
            # Mock queue attributes for throttling check
            mock_sqs.get_queue_attributes.return_value = {
                'Attributes': {
                    'ApproximateNumberOfMessages': '1200',  # High load
                    'ApproximateNumberOfMessagesNotVisible': '300',
                    'ApproximateNumberOfMessagesDelayed': '0'
                }
            }
            
            # Mock batch send
            mock_sqs.send_message_batch.return_value = {
                'Successful': [{'Id': '0', 'MessageId': 'msg-001'}],
                'Failed': []
            }
            
            mock_client.return_value = mock_sqs

            with patch('time.sleep') as mock_sleep:
                result = send_sqs_message_with_throttling(
                    messages, self.queue_url, _get_default_session(), 
                    enable_throttling=True, base_delay=30
                )

            # Should have checked queue depth and applied throttling
            mock_sqs.get_queue_attributes.assert_called_once()
            mock_sleep.assert_called_once_with(60)  # 2x base delay for high load
            mock_sqs.send_message_batch.assert_called_once()
            assert len(result) == 1

    def test_pos_send_sqs_message_with_throttling_disabled(self):
        """Test sending messages with throttling disabled"""
        messages = [{"thing": "device-001", "certificate": "cert1"}]
        
        with patch('boto3.Session.client') as mock_client:
            mock_sqs = MagicMock()
            mock_sqs.send_message_batch.return_value = {
                'Successful': [{'Id': '0', 'MessageId': 'msg-001'}],
                'Failed': []
            }
            mock_client.return_value = mock_sqs

            with patch('time.sleep') as mock_sleep:
                result = send_sqs_message_with_throttling(
                    messages, self.queue_url, _get_default_session(), 
                    enable_throttling=False
                )

            # Should not have checked queue depth or applied throttling
            mock_sqs.get_queue_attributes.assert_not_called()
            mock_sleep.assert_not_called()
            mock_sqs.send_message_batch.assert_called_once()

    def test_pos_send_sqs_message_with_adaptive_throttling(self):
        """Test adaptive throttling with queue depth monitoring"""
        messages = [{"thing": f"device-{i:03d}", "certificate": f"cert{i}"} for i in range(25)]
        
        with patch('boto3.Session.client') as mock_client:
            mock_sqs = MagicMock()
            
            # Mock queue attributes - first check shows high load, second shows normal
            mock_sqs.get_queue_attributes.side_effect = [
                {
                    'Attributes': {
                        'ApproximateNumberOfMessages': '1500',  # High load
                        'ApproximateNumberOfMessagesNotVisible': '200',
                        'ApproximateNumberOfMessagesDelayed': '0'
                    }
                },
                {
                    'Attributes': {
                        'ApproximateNumberOfMessages': '800',   # Normal load
                        'ApproximateNumberOfMessagesNotVisible': '100',
                        'ApproximateNumberOfMessagesDelayed': '0'
                    }
                }
            ]
            
            # Mock batch send
            mock_sqs.send_message_batch.return_value = {
                'Successful': [{'Id': '0', 'MessageId': 'msg-001'}],
                'Failed': []
            }
            
            mock_client.return_value = mock_sqs

            with patch('time.sleep') as mock_sleep:
                result = send_sqs_message_with_adaptive_throttling(
                    messages, self.queue_url, _get_default_session(),
                    max_queue_depth=1000, check_interval=10
                )

            # Should have checked queue depth and applied adaptive throttling
            assert mock_sqs.get_queue_attributes.call_count >= 1
            # Should have applied throttling delay for high load
            throttling_calls = [call for call in mock_sleep.call_args_list if call[0][0] > 1]
            assert len(throttling_calls) >= 1  # At least one throttling delay
            
            # Should have sent all batches
            expected_batches = (len(messages) + 9) // 10  # Round up
            assert mock_sqs.send_message_batch.call_count == expected_batches

    def test_neg_get_queue_depth_client_error(self):
        """Test handling of ClientError in get_queue_depth function"""
        with patch('boto3.Session.client') as mock_client:
            mock_sqs = MagicMock()
            mock_sqs.get_queue_attributes.side_effect = ClientError(
                error_response={'Error': {'Code': 'QueueDoesNotExist', 'Message': 'Queue not found'}},
                operation_name='GetQueueAttributes'
            )
            mock_client.return_value = mock_sqs

            with raises(ClientError) as exc:
                get_queue_depth("invalid-queue-url", _get_default_session())
                
            assert boto_errorcode(exc.value) == 'QueueDoesNotExist'

    def test_pos_send_sqs_message_with_throttling_fallback(self):
        """Test throttling with fallback when queue depth check fails"""
        messages = [{"thing": "device-001", "certificate": "cert1"}]
        
        with patch('boto3.Session.client') as mock_client:
            mock_sqs = MagicMock()
            
            # Mock queue attributes to fail
            mock_sqs.get_queue_attributes.side_effect = ClientError(
                error_response={'Error': {'Code': 'AccessDenied', 'Message': 'Access denied'}},
                operation_name='GetQueueAttributes'
            )
            
            # Mock batch send to succeed
            mock_sqs.send_message_batch.return_value = {
                'Successful': [{'Id': '0', 'MessageId': 'msg-001'}],
                'Failed': []
            }
            
            mock_client.return_value = mock_sqs

            with patch('time.sleep') as mock_sleep:
                result = send_sqs_message_with_throttling(
                    messages, self.queue_url, _get_default_session(), 
                    enable_throttling=True
                )

            # Should have attempted queue depth check but continued without throttling
            mock_sqs.get_queue_attributes.assert_called_once()
            mock_sleep.assert_not_called()  # No throttling delay due to fallback
            mock_sqs.send_message_batch.assert_called_once()
            assert len(result) == 1

    def test_neg_register_certificate_client_error(self):
        """Test handling of ClientError in register_certificate function"""
        invalid_cert = "-----INVALID CERTIFICATE-----"
        
        with patch('boto3.Session.client') as mock_client:
            mock_iot = MagicMock()
            mock_error_response = {
                'Error': {
                    'Code': 'InvalidParameterException',
                    'Message': 'Invalid certificate format'
                }
            }
            mock_iot.register_certificate_without_ca.side_effect = ClientError(
                mock_error_response, 'RegisterCertificateWithoutCA')
            mock_client.return_value = mock_iot

            with raises(ClientError) as exc:
                register_certificate(invalid_cert, _get_default_session())
                
            assert boto_errorcode(exc.value) == 'InvalidParameterException'
            mock_iot.register_certificate_without_ca.assert_called_once()

    def test_neg_process_thing_group_client_error(self):
        """Test handling of ClientError in process_thing_group function"""
        thing_group_arn = "arn:aws:iot:us-east-1:123456789012:thinggroup/nonexistent-group"
        thing_arn = "arn:aws:iot:us-east-1:123456789012:thing/nonexistent-thing"
        
        with patch('boto3.Session.client') as mock_client:
            mock_iot = MagicMock()
            mock_error_response = {
                'Error': {
                    'Code': 'ResourceNotFoundException',
                    'Message': 'Thing group not found'
                }
            }
            mock_iot.add_thing_to_thing_group.side_effect = ClientError(
                mock_error_response, 'AddThingToThingGroup')
            mock_client.return_value = mock_iot

            with raises(ClientError) as exc:
                process_thing_group(thing_group_arn, thing_arn, _get_default_session())
                
            assert boto_errorcode(exc.value) == 'ResourceNotFoundException'
            mock_iot.add_thing_to_thing_group.assert_called_once_with(
                thingGroupArn=thing_group_arn,
                thingArn=thing_arn,
                overrideDynamicGroups=False
            )

    def test_neg_process_thing_describe_client_error(self):
        """Test handling of ClientError in process_thing function when describe_thing fails"""
        thing_name = "nonexistent-thing"
        certificate_id = "certificate-id"
        certificate_arn = "arn:aws:iot:us-east-1:123456789012:cert/certificate-id"
        
        with patch('boto3.Session.client') as mock_client:
            mock_iot = MagicMock()
            # First error for describe_thing
            mock_error_response_describe = {
                'Error': {
                    'Code': 'ResourceNotFoundException',
                    'Message': 'Thing not found'
                }
            }
            mock_iot.describe_thing.side_effect = ClientError(
                mock_error_response_describe, 'DescribeThing')
            
            # Second error for create_thing
            mock_error_response_create = {
                'Error': {
                    'Code': 'ThrottlingException',
                    'Message': 'Rate exceeded'
                }
            }
            mock_iot.create_thing.side_effect = ClientError(
                mock_error_response_create, 'CreateThing')
            
            mock_client.return_value = mock_iot
            
            # Mock get_certificate_arn to return a valid ARN
            with patch('src.layer_utils.layer_utils.aws_utils.get_certificate_arn', return_value=certificate_arn):
                with raises(ClientError) as exc:
                    process_thing(thing_name, certificate_id, session=_get_default_session())
                
                assert boto_errorcode(exc.value) == 'ThrottlingException'
                mock_iot.describe_thing.assert_called_once_with(thingName=thing_name)
                mock_iot.create_thing.assert_called_once_with(thingName=thing_name)

    def test_neg_process_thing_attach_client_error(self):
        """Test handling of ClientError in process_thing function when attach_thing_principal fails"""
        thing_name = "test-thing"
        certificate_id = "certificate-id"
        certificate_arn = "arn:aws:iot:us-east-1:123456789012:cert/certificate-id"
        
        with patch('boto3.Session.client') as mock_client:
            mock_iot = MagicMock()
            # First error for describe_thing
            mock_error_response_describe = {
                'Error': {
                    'Code': 'ResourceNotFoundException',
                    'Message': 'Thing not found'
                }
            }
            mock_iot.describe_thing.side_effect = ClientError(
                mock_error_response_describe, 'DescribeThing')
            
            # No error for create_thing
            mock_iot.create_thing.return_value = {'thingName': thing_name}
            
            # Error for attach_thing_principal
            mock_error_response_attach = {
                'Error': {
                    'Code': 'InvalidRequestException',
                    'Message': 'Cannot attach principal to thing'
                }
            }
            mock_iot.attach_thing_principal.side_effect = ClientError(
                mock_error_response_attach, 'AttachThingPrincipal')
            
            mock_client.return_value = mock_iot
            
            # Mock get_certificate_arn to return a valid ARN
            with patch('src.layer_utils.layer_utils.aws_utils.get_certificate_arn', return_value=certificate_arn):
                with raises(ClientError) as exc:
                    process_thing(thing_name, certificate_id, session=_get_default_session())
                
                assert boto_errorcode(exc.value) == 'InvalidRequestException'
                mock_iot.describe_thing.assert_called_once_with(thingName=thing_name)
                mock_iot.create_thing.assert_called_once_with(thingName=thing_name)
                mock_iot.attach_thing_principal.assert_called_once_with(
                    thingName=thing_name,
                    principal=certificate_arn
                )

    def test_neg_process_thing_type_client_error(self):
        """Test handling of ClientError in process_thing_type function"""
        thing_name = "test-thing"
        thing_type_name = "nonexistent-type"
        
        with patch('boto3.Session.client') as mock_client:
            mock_iot = MagicMock()
            mock_error_response = {
                'Error': {
                    'Code': 'ResourceNotFoundException',
                    'Message': 'Thing type not found'
                }
            }
            mock_iot.update_thing.side_effect = ClientError(
                mock_error_response, 'UpdateThing')
            mock_client.return_value = mock_iot

            with raises(ClientError) as exc:
                process_thing_type(thing_name, thing_type_name, _get_default_session())
                
            assert boto_errorcode(exc.value) == 'ResourceNotFoundException'
            mock_iot.update_thing.assert_called_once_with(
                thingName=thing_name,
                thingTypeName=thing_type_name,
                removeThingType=False
            )

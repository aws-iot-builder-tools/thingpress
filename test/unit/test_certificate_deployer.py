"""
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

Unit tests for certificate_deployer

Tests the Lambda function that deploys Microchip verification certificates
to S3 buckets as part of CloudFormation custom resources.
"""
import os
import base64
from unittest import TestCase
from unittest.mock import patch, MagicMock
from boto3 import _get_default_session
from moto import mock_aws

from src.certificate_deployer.certificate_deployer.main import (
    deploy_certificates,
    lambda_handler
)
import src.certificate_deployer.certificate_deployer.cfnresponse as cfnresponse

@mock_aws(config={
    "core": {
        "mock_credentials": True,
        "reset_boto3_session": False,
        "service_whitelist": None,
    }})
class TestCertificateDeployer(TestCase):
    """Certificate deployer test cases"""

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
        """Set up test fixtures"""
        self.test_bucket_name = "test-verification-certs-bucket"
        self.test_lambda_arn = "arn:aws:lambda:us-east-1:123456789012:function:test-function"

        # Create S3 bucket for testing
        s3_client = self.session.client('s3')
        s3_client.create_bucket(Bucket=self.test_bucket_name)

        # Sample certificate data (base64 encoded)
        self.sample_certificates = {
            "test_cert_1.crt": "LS0tLS1CRUdJTiBDRVJUSUZJQ0FURS0tLS0tCk1JSUIwakNDQVhpZ0F3SUJBZ0lRY1AxNGhMbHdVcGlyM2k4dGR6cm1oVEFLQmdncWhrak9QUVFEQWpCQk1TRXcKSHdZRFZRUUtEQmhOYVdOeWIyTm9hWEFnVkdWamFHNXZiRzluZVNCSmJtTXhIREFhQmdOVkJBTU1FMDFoYm1sbQpaWE4wSUZOcFoyNWxjaUF3TURVd0lCY05NalF3TXpBM01ERXpNakk0V2hnUE9UazVPVEV5TXpFeU16VTVOVGxhCk1FRXhJVEFmQmdOVkJBb01HRTFwWTNKdlkyaHBjQ0JVWldOb2JtOXNiMmQ1SUVsdVl6RWNNQm9HQTFVRUF3d1QKVFdGdWFXWmxjM1FnVTJsbmJtVnlJREF3TlRCWk1CTUdCeXFHU000OUFnRUdDQ3FHU000OUF3RUhBMElBQkV5dgpIZGw5ZWFoR1ZWQjZxQmsxMGhKSm8wTFFZVmJwK1dpRjdiSU5pSHdZamdhRGJheGljVFlVbWh4ZWdmcTE2bk1NCjNXYjhDNWpmc3pCRzNKSWo1SmlqVURCT01CMEdBMVVkRGdRV0JCUk1LZW1mTmdId3pjSTd2dm9ISThuYkpmY3AKaWpBZkJnTlZIU01FR0RBV2dCUk1LZW1mTmdId3pjSTd2dm9ISThuYkpmY3BpakFNQmdOVkhSTUJBZjhFQWpBQQpNQW9HQ0NxR1NNNDlCQU1DQTBnQU1FVUNJRXFvc2d6T2NGNFl1dHVTWmJ3NGQzQ3VuTW1NRTRwWVVpTWhRQ0tHCjlhSG5BaUVBempOWTZZSnh0Z0V3eHpnQlVtWFAxQTVJUzdFblVRQ2JjTGtHVURoM3VNTT0KLS0tLS1FTkQgQ0VSVElGSUNBVEUtLS0tLQo=",
            "test_cert_2.crt": "LS0tLS1CRUdJTiBDRVJUSUZJQ0FURS0tLS0tCk1JSUJ4ekNDQVd5Z0F3SUJBZ0lRYzZIeU1qcmtUMlRPWTE3RkFYN1hWakFLQmdncWhrak9QUVFEQWpBOE1TRXcKSHdZRFZRUUtEQmhOYVdOeWIyTm9hWEFnVkdWamFHNXZiRzluZVNCSmJtTXhGekFWQmdOVkJBTU1Ea3h2WnlCVAphV2R1WlhJZ01EQXlNQjRYRFRFNU1EZ3hOVEU1TkRjMU9Wb1hEVEl3TURneE5URTVORGMxT1Zvd1BERWhNQjhHCkExVUVDZ3dZVFdsamNtOWphR2x3SUZSbFkyaHViMnh2WjNrZ1NXNWpNUmN3RlFZRFZRUUREQTVNYjJjZ1UybG4KYm1WeUlEQXdNakJaTUJNR0J5cUdTTTQ5QWdFR0NDcUdTTTQ5QXdFSEEwSUFCTENMcmdQbFQzT2V6bnREOWxDMgpTaHdVaGx4MDdmaXEvVkVUSitJVFVBd2JnclBqQi9YaTlHY2hMSU03RndaU1VHT0VxUkE2S3RIMzJYTXBUR0hLCm1DQ2pVREJPTUIwR0ExVWREZ1FXQkJUeFY0b1ozSlRaM3pCNi9yOVhNMGs0RTYvNXdEQWZCZ05WSFNNRUdEQVcKZ0JUeFY0b1ozSlRaM3pCNi9yOVhNMGs0RTYvNXdEQU1CZ05WSFJNQkFmOEVBakFBTUFvR0NDcUdTTTQ5QkFNQwpBMGtBTUVZQ0lRREtIZ2N0TG5xL3pOcWZCKzF2MEtSaERWUHZSZjZEaW10OGFXOVdMUzBOV0FJaEFKdlVlM3VKCnBrTUc0enBvdjlGQ29qNEczNDBpZEVhZG03bVZiQWQ1R09COQotLS0tLUVORCBDRVJUSUZJQ0FURS0tLS0tCg=="
        }

        # Sample CloudFormation event
        self.sample_cfn_event = {
            'RequestType': 'Create',
            'ResponseURL': 'https://cloudformation-custom-resource-response-useast1.s3.amazonaws.com/test',
            'StackId': 'arn:aws:cloudformation:us-east-1:123456789012:stack/test-stack/12345',
            'RequestId': 'test-request-id',
            'LogicalResourceId': 'TestResource',
            'ResourceProperties': {
                'BucketName': self.test_bucket_name,
                'Certificates': self.sample_certificates
            }
        }
        
        # Sample S3 notification configuration event
        self.sample_notification_event = {
            'RequestType': 'Create',
            'ResponseURL': 'https://cloudformation-custom-resource-response-useast1.s3.amazonaws.com/test',
            'StackId': 'arn:aws:cloudformation:us-east-1:123456789012:stack/test-stack/12345',
            'RequestId': 'test-request-id',
            'LogicalResourceId': 'TestNotificationResource',
            'ResourceProperties': {
                'BucketName': self.test_bucket_name,
                'NotificationConfiguration': {
                    'LambdaFunctionConfigurations': [{
                        'LambdaFunctionArn': self.test_lambda_arn,
                        'Event': 's3:ObjectCreated:*'
                    }]
                }
            }
        }

    def _create_mock_context(self):
        """Create a properly configured mock context"""
        mock_context = MagicMock()
        mock_context.log_stream_name = 'test-log-stream-2025/07/21/[$LATEST]abcdef123456'
        return mock_context

    def tearDown(self):
        """Clean up test fixtures"""
        s3_resource = self.session.resource("s3")
        s3_bucket = s3_resource.Bucket(self.test_bucket_name)
        
        # Delete all objects in bucket
        for key in s3_bucket.objects.all():
            key.delete()
        
        # Delete bucket
        s3_bucket.delete()

    def test_deploy_certificates_success(self):
        """Test successful certificate deployment"""
        result = deploy_certificates(self.test_bucket_name, self.sample_certificates)
        
        self.assertTrue(result)
        
        # Verify certificates were uploaded
        s3_client = self.session.client('s3')
        
        for cert_name in self.sample_certificates.keys():
            response = s3_client.get_object(
                Bucket=self.test_bucket_name,
                Key=cert_name
            )
            
            # Verify content matches
            uploaded_content = response['Body'].read()
            expected_content = base64.b64decode(self.sample_certificates[cert_name])
            self.assertEqual(uploaded_content, expected_content)

    def test_deploy_certificates_failure(self):
        """Test certificate deployment failure handling"""
        # Use non-existent bucket to trigger failure
        result = deploy_certificates("non-existent-bucket", self.sample_certificates)

        self.assertFalse(result)

    @patch('src.certificate_deployer.certificate_deployer.cfnresponse.send')
    def test_lambda_handler_certificate_deployment_create(self, mock_cfn_send):
        """Test Lambda handler for certificate deployment Create request"""
        mock_context = self._create_mock_context()
        
        lambda_handler(self.sample_cfn_event, mock_context)
        
        # Verify CloudFormation response was sent
        mock_cfn_send.assert_called_once()
        args = mock_cfn_send.call_args
        
        self.assertEqual(args[0][2], cfnresponse.SUCCESS)  # status
        
        # Verify certificates were deployed
        s3_client = self.session.client('s3')
        for cert_name in self.sample_certificates.keys():
            response = s3_client.get_object(
                Bucket=self.test_bucket_name,
                Key=cert_name
            )
            self.assertIsNotNone(response['Body'])

    @patch('src.certificate_deployer.certificate_deployer.cfnresponse.send')
    def test_lambda_handler_certificate_deployment_update(self, mock_cfn_send):
        """Test Lambda handler for certificate deployment Update request"""
        mock_context = self._create_mock_context()
        update_event = self.sample_cfn_event.copy()
        update_event['RequestType'] = 'Update'

        lambda_handler(update_event, mock_context)

        # Verify CloudFormation response was sent
        mock_cfn_send.assert_called_once()
        args = mock_cfn_send.call_args

        self.assertEqual(args[0][2], cfnresponse.SUCCESS)  # status

    @patch('src.certificate_deployer.certificate_deployer.cfnresponse.send')
    def test_lambda_handler_certificate_deployment_delete(self, mock_cfn_send):
        """Test Lambda handler for certificate deployment Delete request"""
        mock_context = self._create_mock_context()
        delete_event = self.sample_cfn_event.copy()
        delete_event['RequestType'] = 'Delete'

        lambda_handler(delete_event, mock_context)
        
        # Verify CloudFormation response was sent
        mock_cfn_send.assert_called_once()
        args = mock_cfn_send.call_args
        
        self.assertEqual(args[0][2], cfnresponse.SUCCESS)  # status

    @patch('src.certificate_deployer.certificate_deployer.cfnresponse.send')
    def test_lambda_handler_missing_bucket_name(self, mock_cfn_send):
        """Test Lambda handler with missing BucketName property"""
        mock_context = self._create_mock_context()
        invalid_event = self.sample_cfn_event.copy()
        del invalid_event['ResourceProperties']['BucketName']
        
        lambda_handler(invalid_event, mock_context)
        
        # Verify failure response was sent
        mock_cfn_send.assert_called_once()
        args = mock_cfn_send.call_args

        self.assertEqual(args[0][2], cfnresponse.FAILED)  # status

    @patch('src.certificate_deployer.certificate_deployer.cfnresponse.send')
    def test_lambda_handler_deployment_failure(self, mock_cfn_send):
        """Test Lambda handler when certificate deployment fails"""
        mock_context = self._create_mock_context()

        # Use invalid bucket name to trigger failure
        failure_event = self.sample_cfn_event.copy()
        failure_event['ResourceProperties']['BucketName'] = "invalid-bucket-name-that-does-not-exist"

        lambda_handler(failure_event, mock_context)

        # Verify failure response was sent
        mock_cfn_send.assert_called_once()
        args = mock_cfn_send.call_args

        self.assertEqual(args[0][2], cfnresponse.FAILED)  # status

    def test_deploy_certificates_empty_certificates(self):
        """Test deploying empty certificate dictionary"""
        result = deploy_certificates(self.test_bucket_name, {})

        self.assertTrue(result)  # Should succeed with no certificates to deploy

    @patch('src.certificate_deployer.certificate_deployer.cfnresponse.send')
    def test_lambda_handler_exception_handling(self, mock_cfn_send):
        """Test Lambda handler exception handling"""
        mock_context = self._create_mock_context()

        # Create event that will cause an exception (invalid JSON structure)
        invalid_event = {
            'RequestType': 'Create',
            'ResponseURL': 'https://test.com',
            'StackId': 'test-stack',
            'RequestId': 'test-request',
            'LogicalResourceId': 'TestResource',
            'ResourceProperties': None  # This will cause an exception
        }
        
        lambda_handler(invalid_event, mock_context)
        
        # Verify failure response was sent
        mock_cfn_send.assert_called_once()
        args = mock_cfn_send.call_args
        
        self.assertEqual(args[0][2], cfnresponse.FAILED)  # status

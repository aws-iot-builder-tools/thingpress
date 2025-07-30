"""
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

Unit tests for certificate_deployer

Tests the Lambda function that deploys Microchip verification certificates
to S3 buckets as part of CloudFormation custom resources.
"""
import os
import json
import base64
from unittest import TestCase
from unittest.mock import patch, MagicMock
from boto3 import Session, _get_default_session
from moto import mock_aws
from botocore.exceptions import ClientError

from src.certificate_deployer.certificate_deployer.main import (
    disable_bucket_notifications,
    configure_bucket_notifications,
    deploy_certificates,
    handle_s3_notification_config,
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

    def test_disable_bucket_notifications_empty_config(self):
        """Test disabling notifications on bucket with no existing notifications"""
        result = disable_bucket_notifications(self.test_bucket_name)
        
        # Should return empty config
        self.assertEqual(result, {})

    def test_disable_bucket_notifications_with_existing_config(self):
        """Test disabling notifications on bucket with existing notifications"""
        s3_client = self.session.client('s3')
        
        # Set up initial notification configuration
        initial_config = {
            'LambdaFunctionConfigurations': [{
                'LambdaFunctionArn': self.test_lambda_arn,
                'Events': ['s3:ObjectCreated:*']
            }]
        }
        
        s3_client.put_bucket_notification_configuration(
            Bucket=self.test_bucket_name,
            NotificationConfiguration=initial_config
        )
        
        # Test disabling notifications
        result = disable_bucket_notifications(self.test_bucket_name)
        
        # Should return the previous configuration
        self.assertIn('LambdaFunctionConfigurations', result)
        self.assertEqual(len(result['LambdaFunctionConfigurations']), 1)
        
        # Verify notifications are actually disabled
        current_config = s3_client.get_bucket_notification_configuration(
            Bucket=self.test_bucket_name
        )
        self.assertNotIn('LambdaFunctionConfigurations', current_config)

    def test_configure_bucket_notifications_restore(self):
        """Test restoring bucket notifications from previous configuration"""
        notification_config = {
            'LambdaFunctionConfigurations': [{
                'LambdaFunctionArn': self.test_lambda_arn,
                'Events': ['s3:ObjectCreated:*']
            }]
        }
        
        configure_bucket_notifications(self.test_bucket_name, notification_config)
        
        # Verify notifications were configured
        s3_client = self.session.client('s3')
        current_config = s3_client.get_bucket_notification_configuration(
            Bucket=self.test_bucket_name
        )
        
        self.assertIn('LambdaFunctionConfigurations', current_config)
        self.assertEqual(len(current_config['LambdaFunctionConfigurations']), 1)

    def test_configure_bucket_notifications_new_lambda(self):
        """Test configuring notifications with new Lambda ARN"""
        configure_bucket_notifications(
            self.test_bucket_name, 
            lambda_arn=self.test_lambda_arn
        )
        
        # Verify notifications were configured
        s3_client = self.session.client('s3')
        current_config = s3_client.get_bucket_notification_configuration(
            Bucket=self.test_bucket_name
        )
        
        self.assertIn('LambdaFunctionConfigurations', current_config)
        lambda_config = current_config['LambdaFunctionConfigurations'][0]
        self.assertEqual(lambda_config['LambdaFunctionArn'], self.test_lambda_arn)

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

    def test_handle_s3_notification_config_create(self):
        """Test handling S3 notification configuration for Create request"""
        mock_context = self._create_mock_context()
        
        result = handle_s3_notification_config(self.sample_notification_event, mock_context)
        
        # Verify function returned success
        self.assertTrue(result)
        
        # Verify notifications were configured
        s3_client = self.session.client('s3')
        current_config = s3_client.get_bucket_notification_configuration(
            Bucket=self.test_bucket_name
        )
        
        self.assertIn('LambdaFunctionConfigurations', current_config)

    def test_handle_s3_notification_config_delete(self):
        """Test handling S3 notification configuration for Delete request"""
        mock_context = self._create_mock_context()
        delete_event = self.sample_notification_event.copy()
        delete_event['RequestType'] = 'Delete'
        
        result = handle_s3_notification_config(delete_event, mock_context)
        
        # Verify function returned success
        self.assertTrue(result)
        
        # Verify notifications were cleared
        s3_client = self.session.client('s3')
        current_config = s3_client.get_bucket_notification_configuration(
            Bucket=self.test_bucket_name
        )
        
        # Should not have any notification configurations
        self.assertNotIn('LambdaFunctionConfigurations', current_config)

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
    def test_lambda_handler_s3_notification_config(self, mock_cfn_send):
        """Test Lambda handler for S3 notification configuration"""
        mock_context = self._create_mock_context()
        
        lambda_handler(self.sample_notification_event, mock_context)
        
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

    def test_configure_bucket_notifications_complex_config(self):
        """Test configuring bucket notifications with complex configuration"""
        complex_config = {
            'LambdaFunctionConfigurations': [{
                'LambdaFunctionArn': self.test_lambda_arn,
                'Events': ['s3:ObjectCreated:*', 's3:ObjectRemoved:*'],
                'Filter': {
                    'Key': {
                        'FilterRules': [{
                            'Name': 'prefix',
                            'Value': 'certificates/'
                        }]
                    }
                }
            }],
            'TopicConfigurations': [{
                'TopicArn': 'arn:aws:sns:us-east-1:123456789012:test-topic',
                'Events': ['s3:ObjectCreated:*']
            }]
        }
        
        configure_bucket_notifications(self.test_bucket_name, complex_config)
        
        # Verify complex configuration was applied
        s3_client = self.session.client('s3')
        current_config = s3_client.get_bucket_notification_configuration(
            Bucket=self.test_bucket_name
        )
        
        self.assertIn('LambdaFunctionConfigurations', current_config)
        self.assertIn('TopicConfigurations', current_config)
        
        lambda_config = current_config['LambdaFunctionConfigurations'][0]
        self.assertEqual(len(lambda_config['Events']), 2)
        self.assertIn('Filter', lambda_config)

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

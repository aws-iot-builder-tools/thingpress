"""
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

Unit tests for cfnresponse module

Tests the CloudFormation custom resource response helper functions.
"""
import json
from unittest import TestCase
from unittest.mock import patch, MagicMock
from urllib.error import URLError

from src.certificate_deployer.certificate_deployer.cfnresponse import CfnResponse, SUCCESS, FAILED


class TestCfnResponse(TestCase):
    """CloudFormation response helper test cases"""

    def setUp(self):
        """Set up test fixtures"""
        self.sample_event = {
            'ResponseURL': 'https://cloudformation-custom-resource-response-useast1.s3.amazonaws.com/test',
            'StackId': 'arn:aws:cloudformation:us-east-1:123456789012:stack/test-stack/12345',
            'RequestId': 'test-request-id',
            'LogicalResourceId': 'TestResource'
        }
        
        self.sample_context = MagicMock()
        self.sample_context.log_stream_name = 'test-log-stream'
        
        self.sample_response_data = {
            'Message': 'Test operation completed successfully'
        }

    @patch('urllib.request.urlopen')
    def test_send_success_response(self, mock_urlopen):
        """Test sending successful CloudFormation response"""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.reason = 'OK'
        mock_urlopen.return_value = mock_response

        response = CfnResponse()
        response.response_url = self.sample_event["ResponseURL"]
        response.stack_id = self.sample_event["StackId"]
        response.request_id = self.sample_event["RequestId"]
        response.logical_resource_id = self.sample_event["LogicalResourceId"]
        response.physical_resource_id = 'test-physical-id'
        response.status = True
        response.data = self.sample_response_data
        response.send()
        
        # Verify urlopen was called
        mock_urlopen.assert_called_once()
        
        # Get the request that was made
        call_args = mock_urlopen.call_args
        request = call_args[0][0]
        
        # Verify the request URL
        self.assertEqual(request.full_url, self.sample_event['ResponseURL'])
        
        # Verify the request method
        self.assertEqual(request.get_method(), 'PUT')
        
        # Verify the request data
        request_data = json.loads(request.data.decode('utf-8'))
        self.assertEqual(request_data['Status'], SUCCESS)
        self.assertEqual(request_data['RequestId'], self.sample_event['RequestId'])
        self.assertEqual(request_data['StackId'], self.sample_event['StackId'])
        self.assertEqual(request_data['LogicalResourceId'], self.sample_event['LogicalResourceId'])
        self.assertEqual(request_data['PhysicalResourceId'], 'test-physical-id')
        self.assertEqual(request_data['Data'], self.sample_response_data)

    @patch('urllib.request.urlopen')
    def test_send_failure_response(self, mock_urlopen):
        """Test sending failure CloudFormation response"""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.reason = 'OK'
        mock_urlopen.return_value = mock_response

        response = CfnResponse()
        response.response_url = self.sample_event["ResponseURL"]
        response.stack_id = self.sample_event["StackId"]
        response.request_id = self.sample_event["RequestId"]
        response.logical_resource_id = self.sample_event["LogicalResourceId"]
        response.status = False
        response.data = {'Error': 'Test error occurred'}
        response.send()
        
        # Verify urlopen was called
        mock_urlopen.assert_called_once()
        
        # Get the request data
        call_args = mock_urlopen.call_args
        request = call_args[0][0]
        request_data = json.loads(request.data.decode('utf-8'))
        
        self.assertEqual(request_data['Status'], FAILED)
        self.assertEqual(request_data['Data'], {'Error': 'Test error occurred'})

    @patch('urllib.request.urlopen')
    def test_send_with_default_physical_resource_id(self, mock_urlopen):
        """Test sending response with default physical resource ID"""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.reason = 'OK'
        mock_urlopen.return_value = mock_response
        
        response = CfnResponse()
        response.response_url = self.sample_event["ResponseURL"]
        response.stack_id = self.sample_event["StackId"]
        response.request_id = self.sample_event["RequestId"]
        response.logical_resource_id = self.sample_event["LogicalResourceId"]
        response.physical_resource_id = self.sample_context.log_stream_name

        response.status = True
        response.data = self.sample_response_data
        response.send()
        
        # Get the request data
        call_args = mock_urlopen.call_args
        request = call_args[0][0]
        request_data = json.loads(request.data.decode('utf-8'))
        
        # Should use log stream name as default physical resource ID
        self.assertEqual(request_data['PhysicalResourceId'], 'test-log-stream')

    @patch('urllib.request.urlopen')
    def test_send_with_no_echo(self, mock_urlopen):
        """Test sending response with noEcho flag"""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.reason = 'OK'
        mock_urlopen.return_value = mock_response
        
        response = CfnResponse()
        response.response_url = self.sample_event["ResponseURL"]
        response.stack_id = self.sample_event["StackId"]
        response.request_id = self.sample_event["RequestId"]
        response.logical_resource_id = self.sample_event["LogicalResourceId"]
        response.status = True
        response.data = self.sample_response_data
        response.no_echo = True
        response.send()
        
        # Get the request data
        call_args = mock_urlopen.call_args
        request = call_args[0][0]
        request_data = json.loads(request.data.decode('utf-8'))
        
        self.assertTrue(request_data['NoEcho'])

    @patch('urllib.request.urlopen')
    def test_send_with_no_echo_false(self, mock_urlopen):
        """Test sending response with noEcho flag set to False"""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.reason = 'OK'
        mock_urlopen.return_value = mock_response
        
        response = CfnResponse()
        response.response_url = self.sample_event["ResponseURL"]
        response.stack_id = self.sample_event["StackId"]
        response.request_id = self.sample_event["RequestId"]
        response.logical_resource_id = self.sample_event["LogicalResourceId"]
        response.status = True
        response.data = self.sample_response_data
        response.no_echo = False
        response.send()

        # Get the request data
        call_args = mock_urlopen.call_args
        request = call_args[0][0]
        request_data = json.loads(request.data.decode('utf-8'))
        
        self.assertFalse(request_data['NoEcho'])

    @patch('urllib.request.urlopen')
    def test_send_handles_url_error(self, mock_urlopen):
        """Test that send handles URLError gracefully"""
        mock_urlopen.side_effect = URLError('Connection failed')
        
        # Should raise the exception (proper error handling)
        with self.assertRaises(URLError):
            response = CfnResponse()
            response.response_url = self.sample_event["ResponseURL"]
            response.stack_id = self.sample_event["StackId"]
            response.request_id = self.sample_event["RequestId"]
            response.logical_resource_id = self.sample_event["LogicalResourceId"]
            response.status = True
            response.data = self.sample_response_data
            response.send()

    @patch('urllib.request.urlopen')
    def test_send_handles_general_exception(self, mock_urlopen):
        """Test that send handles general exceptions gracefully"""
        mock_urlopen.side_effect = Exception('Unexpected error')
        
        # Should raise the exception (proper error handling)
        with self.assertRaises(Exception):
            response = CfnResponse()
            response.response_url = self.sample_event["ResponseURL"]
            response.stack_id = self.sample_event["StackId"]
            response.request_id = self.sample_event["RequestId"]
            response.logical_resource_id = self.sample_event["LogicalResourceId"]
            response.status = True
            response.data = self.sample_response_data
            response.send()

    @patch('urllib.request.urlopen')
    def test_send_request_headers(self, mock_urlopen):
        """Test that send sets correct request headers"""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.reason = 'OK'
        mock_urlopen.return_value = mock_response
        
        response = CfnResponse()
        response.response_url = self.sample_event["ResponseURL"]
        response.stack_id = self.sample_event["StackId"]
        response.request_id = self.sample_event["RequestId"]
        response.logical_resource_id = self.sample_event["LogicalResourceId"]
        response.status = True
        response.data = self.sample_response_data
        response.send()
        
        # Get the request that was made
        call_args = mock_urlopen.call_args
        request = call_args[0][0]
        
        # Verify Content-Type header
        self.assertEqual(request.get_header('Content-type'), '')
        self.assertEqual(request.get_header('Content-length'), str(len(request.data)))

    @patch('urllib.request.urlopen')
    def test_send_empty_response_data(self, mock_urlopen):
        """Test sending response with empty response data"""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.reason = 'OK'
        mock_urlopen.return_value = mock_response
        
        response = CfnResponse()
        response.response_url = self.sample_event["ResponseURL"]
        response.stack_id = self.sample_event["StackId"]
        response.request_id = self.sample_event["RequestId"]
        response.logical_resource_id = self.sample_event["LogicalResourceId"]
        response.status = True
        response.data = {}
        response.send()
        
        # Get the request data
        call_args = mock_urlopen.call_args
        request = call_args[0][0]
        request_data = json.loads(request.data.decode('utf-8'))
        
        self.assertEqual(request_data['Data'], {})

    @patch('urllib.request.urlopen')
    def test_send_none_response_data(self, mock_urlopen):
        """Test sending response with None response data"""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.reason = 'OK'
        mock_urlopen.return_value = mock_response
        
        response = CfnResponse()
        response.response_url = self.sample_event["ResponseURL"]
        response.stack_id = self.sample_event["StackId"]
        response.request_id = self.sample_event["RequestId"]
        response.logical_resource_id = self.sample_event["LogicalResourceId"]
        response.status = True
        response.data = None
        response.send()
        
        # Get the request data
        call_args = mock_urlopen.call_args
        request = call_args[0][0]
        request_data = json.loads(request.data.decode('utf-8'))
        
        self.assertIsNone(request_data['Data'])

    def test_constants(self):
        """Test that SUCCESS and FAILED constants are defined correctly"""
        self.assertEqual(SUCCESS, "SUCCESS")
        self.assertEqual(FAILED, "FAILED")

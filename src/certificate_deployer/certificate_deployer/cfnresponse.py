# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""CloudFormation custom resource response helper module.
   Provides functionality to send responses back to CloudFormation for custom resources.
"""

import json
import urllib.request
import urllib.error
from aws_lambda_powertools import Logger

logger = Logger()

SUCCESS = "SUCCESS"
FAILED = "FAILED"

class CfnResponse():
    """CfnResponse composes all the required wiring for handling CloudFormation custom resource
       responses to a CloudFormation stack in Create/Update/Delete states.
    """
    # pylint: disable=too-many-instance-attributes
    # Configurable attributes for each separate line in the response body (8)

    def __init__(self):
        self._response_url = None
        self._status: str = SUCCESS
        self._reason = None
        self._physical_resource_id = None
        self._stack_id = None
        self._request_id = None
        self._logical_resource_id = None
        self._no_echo = None
        self._data = None

    @property
    def response_url(self):
        """Property definition for response_url"""
        return self._response_url
    @response_url.setter
    def response_url(self, value):
        """ often expects lambda event['ResponseURL'] """
        self._response_url = value
    @response_url.getter
    def response_url(self):
        """Getter for the response_url property"""
        return self._response_url

    @property
    def status(self):
        """Property definition for status. True->SUCCESS, False->FAILED"""
        return self._status
    @status.setter
    def status(self, value: bool):
        if value is True:
            self._status = SUCCESS
        else:
            self._status = FAILED
    @status.getter
    def status(self):
        """Getter for the status property"""
        return self._status

    @property
    def reason(self):
        """Property defintion for reason, unfortunately expects only
        cloudwatch log stream
        """
        return self._reason
    @reason.setter
    def reason(self, value):
        """ expects context.log_stream_name """
        self._reason =  'See the details in CloudWatch Log Stream: ' + value
    @reason.getter
    def reason(self):
        """Getter for the reason property"""
        return self._reason

    @property
    def physical_resource_id(self):
        """Property definition for physical_resource_id"""
        return self._physical_resource_id
    @physical_resource_id.setter
    def physical_resource_id(self, value):
        """ self-defined, alternatively (lambda)context.log_stream_name """
        self._physical_resource_id = value
    @physical_resource_id.getter
    def physical_resource_id(self):
        """Getter for the physical_resource_id property"""
        return self._physical_resource_id

    @property
    def stack_id(self):
        """Property definition for stack_id"""
        return self._stack_id
    @stack_id.setter
    def stack_id(self, value):
        """ event['StackId'] """
        self._stack_id = value
    @stack_id.getter
    def stack_id(self):
        """Getter for the stack_id property"""
        return self._stack_id

    @property
    def request_id(self):
        """Property definition for request_id"""
        return self._request_id
    @request_id.setter
    def request_id(self, value):
        """event['RequestId']"""
        self._request_id = value
    @request_id.getter
    def request_id(self):
        """Getter for the request_id property"""
        return self._request_id

    @property
    def logical_resource_id(self):
        """Property definition for logical_resource_id"""
        return self._logical_resource_id
    @logical_resource_id.setter
    def logical_resource_id(self, value):
        """event['LogicalResourceId']"""
        self._logical_resource_id = value
    @logical_resource_id.getter
    def logical_resource_id(self):
        """Getter for the logical_resource_id property"""
        return self._logical_resource_id

    @property
    def no_echo(self):
        """Property definition for no_echo"""
        return self._no_echo
    @no_echo.setter
    def no_echo(self, value):
        self._no_echo = value
    @no_echo.getter
    def no_echo(self):
        """Getter for the no_echo property"""
        return self._no_echo

    @property
    def data(self):
        """Property defintion for data, usually a descriptive context-aware message"""
        return self._data
    @data.setter
    def data(self, value):
        self._data = value
    @data.getter
    def data(self):
        """Getter for the data property"""
        return self._data

    def _get_response_body(self) -> str:
        """Private method for constructing the cloudformation response body"""
        response_body = {
            'Status': self.status,
            'Reason': self.reason,
            'PhysicalResourceId': self.physical_resource_id,
            'StackId': self.stack_id,
            'RequestId': self.request_id,
            'LogicalResourceId': self.logical_resource_id,
            'NoEcho': self.no_echo,
            'Data': self.data
        }

        json_response_body = json.dumps(response_body)

        logger.debug("CloudFormation response body", extra={
            "response_body": json_response_body
        })

        return json_response_body

    def send(self) -> None:
        """ Send a response to CloudFormation regarding the success or failure of
        a custom resource.
        """
        assert self.response_url is not None

        response_url = self.response_url
        response_body = self._get_response_body()

        logger.info("Sending CloudFormation response", extra={
            "response_url": response_url,
            "status": self.status
        })
        headers = {
            'content-type': '',
            'content-length': str(len(response_body))
        }

        # Note: per documentation, exceptions not thrown by creation
        # of the Request object. Infers no parameter validate?
        req = urllib.request.Request(response_url,
                                    data=response_body.encode('utf-8'),
                                    headers=headers,
                                    method='PUT')

        # pylint: disable=too-many-try-statements
        # This is a reasonable pattern and as such cannot be separated into
        # multiple try-except
        try:
            with urllib.request.urlopen(req) as response:
                logger.info("CloudFormation response sent successfully", extra={
                    "status_code": response.status,
                    "reason": response.reason
                })
        except urllib.error.URLError as url_error:
            logger.error("Failed to send CloudFormation response", extra={
                "error": str(url_error),
                "response_url": response_url
            })
            raise

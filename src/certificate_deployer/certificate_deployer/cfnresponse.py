# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""CloudFormation custom resource response helper module.

Provides functionality to send responses back to CloudFormation for custom resources.
Uses AWS Lambda Powertools for structured logging.
"""

import json
import urllib.request
import urllib.error
from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.data_classes import CloudFormationCustomResourceEvent

logger = Logger()

SUCCESS = "SUCCESS"
FAILED = "FAILED"

def send(event: CloudFormationCustomResourceEvent,
         context,
         response_status,
         response_data,
         physical_resource_id=None,
         no_echo=False):
    """ Send a response to CloudFormation regarding the success or failure of
    a custom resource.
    
    Args:
        event (dict): CloudFormation custom resource event
        context (LambdaContext): Lambda execution context
        response_status (str): SUCCESS or FAILED
        response_data (dict): Response data to send back to CloudFormation
        physical_resource_id (str, optional): Physical resource ID
        no_echo (bool, optional): Whether to mask the response
        
    Returns:
        None
    """
    response_url = event['ResponseURL']

    logger.info("Sending CloudFormation response", extra={
        "response_url": response_url,
        "status": response_status
    })

    response_body = {
        'Status': response_status,
        'Reason': 'See the details in CloudWatch Log Stream: ' + context.log_stream_name,
        'PhysicalResourceId': physical_resource_id or context.log_stream_name,
        'StackId': event['StackId'],
        'RequestId': event['RequestId'],
        'LogicalResourceId': event['LogicalResourceId'],
        'NoEcho': no_echo,
        'Data': response_data
    }

    json_response_body = json.dumps(response_body)

    logger.debug("CloudFormation response body", extra={
        "response_body": json_response_body
    })

    headers = {
        'content-type': '',
        'content-length': str(len(json_response_body))
    }

    # Note: per documentation, exceptions not thrown by creation
    # of the Request object.
    req = urllib.request.Request(response_url,
                                 data=json_response_body.encode('utf-8'),
                                 headers=headers,
                                 method='PUT')
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

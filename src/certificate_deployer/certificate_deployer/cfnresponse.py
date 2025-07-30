# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
CloudFormation custom resource response helper module.

Provides functionality to send responses back to CloudFormation for custom resources.
Uses AWS Lambda Powertools for structured logging.
"""

import json
import urllib.request

from aws_lambda_powertools import Logger

logger = Logger()

SUCCESS = "SUCCESS"
FAILED = "FAILED"

def send(event, context, response_status, response_data, physical_resource_id=None, no_echo=False):
    """
    Send a response to CloudFormation regarding the success or failure of a custom resource.
    
    Args:
        event (dict): CloudFormation custom resource event
        context (LambdaContext): Lambda execution context
        responseStatus (str): SUCCESS or FAILED
        responseData (dict): Response data to send back to CloudFormation
        physicalResourceId (str, optional): Physical resource ID
        noEcho (bool, optional): Whether to mask the response
        
    Returns:
        None
    """
    response_url = event['ResponseURL']

    logger.info("Sending CloudFormation response", extra={
        "response_url": response_url,
        "status": response_status
    })

    response_body = {}
    response_body['Status'] = response_status
    response_body['Reason'] = 'See the details in CloudWatch Log Stream: ' + context.log_stream_name
    response_body['PhysicalResourceId'] = physical_resource_id or context.log_stream_name
    response_body['StackId'] = event['StackId']
    response_body['RequestId'] = event['RequestId']
    response_body['LogicalResourceId'] = event['LogicalResourceId']
    response_body['NoEcho'] = no_echo
    response_body['Data'] = response_data

    json_response_body = json.dumps(response_body)

    logger.debug("CloudFormation response body", extra={
        "response_body": json_response_body
    })

    headers = {
        'content-type': '',
        'content-length': str(len(json_response_body))
    }

    try:
        req = urllib.request.Request(response_url,
                                     data=json_response_body.encode('utf-8'),
                                     headers=headers,
                                     method='PUT')
        response = urllib.request.urlopen(req)
        logger.info("CloudFormation response sent successfully", extra={
            "status_code": response.status,
            "reason": response.reason
        })
    except Exception as e:
        logger.error("Failed to send CloudFormation response", extra={
            "error": str(e),
            "response_url": response_url
        })
        # Re-raise the exception so calling code can handle it appropriately
        raise

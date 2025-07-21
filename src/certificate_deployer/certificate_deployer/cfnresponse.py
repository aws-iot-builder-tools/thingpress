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

def send(event, context, responseStatus, responseData, physicalResourceId=None, noEcho=False):
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
    responseUrl = event['ResponseURL']

    logger.info("Sending CloudFormation response", extra={
        "response_url": responseUrl,
        "status": responseStatus
    })

    responseBody = {}
    responseBody['Status'] = responseStatus
    responseBody['Reason'] = 'See the details in CloudWatch Log Stream: ' + context.log_stream_name
    responseBody['PhysicalResourceId'] = physicalResourceId or context.log_stream_name
    responseBody['StackId'] = event['StackId']
    responseBody['RequestId'] = event['RequestId']
    responseBody['LogicalResourceId'] = event['LogicalResourceId']
    responseBody['NoEcho'] = noEcho
    responseBody['Data'] = responseData

    json_responseBody = json.dumps(responseBody)

    logger.debug("CloudFormation response body", extra={
        "response_body": json_responseBody
    })

    headers = {
        'content-type': '',
        'content-length': str(len(json_responseBody))
    }

    try:
        req = urllib.request.Request(responseUrl,
                                     data=json_responseBody.encode('utf-8'),
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
            "response_url": responseUrl
        })
        # Re-raise the exception so calling code can handle it appropriately
        raise

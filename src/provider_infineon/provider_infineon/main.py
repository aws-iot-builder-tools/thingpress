"""
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

Lambda function to decompose Infineon based certificate manifest(s) and begin
the import processing pipeline
"""
import os
import json
import logging
from botocore.exceptions import ClientError
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.utilities.data_classes import SQSEvent
from aws_utils import verify_queue
from aws_utils import boto_errorcode, boto_errormessage
from .manifest_handler import invoke_export, verify_certtype

logger = logging.getLogger()
logger.setLevel("INFO")

def lambda_handler(event: SQSEvent, context: LambdaContext) -> dict: # pylint: disable=unused-argument
    """
    Process Infineon certificate manifests from SQS messages and forward to target queue.
    
    This Lambda function processes SQS messages containing S3 bucket and object information
    for Infineon certificate manifests. For each manifest:
    1. Validates the target SQS queue exists and is accessible
    2. Verifies the certificate type is valid (E0E0, E0E1, or E0E2)
    3. Extracts the appropriate certificate bundle from the 7z archive based on certificate type
    4. Processes each certificate in the bundle, formatting it correctly
    5. Extracts the Common Name (CN) from each certificate for Thing name
    6. Forwards the certificate data to the target SQS queue for further processing
    
    Environment variables:
        QUEUE_TARGET: URL of the SQS queue to forward processed certificates to
        CERT_TYPE: Type of Infineon certificate to process (E0E0, E0E1, or E0E2)
    
    Args:
        event (dict): SQS event containing messages with S3 bucket/object information
        context (LambdaContext): Lambda execution context (unused)
        
    Returns:
        dict: The original event for AWS Lambda SQS batch processing, or None if validation fails
    """
    queue_url = os.environ['QUEUE_TARGET']
    cert_type = os.environ['CERT_TYPE']

    try:
        verify_queue(queue_url=queue_url)
    except ClientError as error:
        error_code = boto_errorcode(error)
        error_message = boto_errormessage(error)
        logger.error("Queue %s is not available. %s: %s", queue_url, error_code, error_message)
        raise error

    try:
        verify_certtype(cert_type)
    except ValueError as error:
        logger.error("Certificate type %s did not verify: %s", queue_url, str(error))
        raise error

    for record in event.records:
        config = json.loads(record["body"])
        invoke_export(config, queue_url, cert_type)

    return event.raw_event

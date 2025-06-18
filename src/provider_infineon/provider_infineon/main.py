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
from .manifest_handler import invoke_export, verify_certtype

logger = logging.getLogger()
logger.setLevel("INFO")

def lambda_handler(event: dict, context: LambdaContext) -> dict: # pylint: disable=unused-argument
    """Lambda function main entry point"""
    sqs_event = SQSEvent(event)
    queue_url = os.environ['QUEUE_TARGET']
    cert_type = os.environ['CERT_TYPE']

    try:
        verify_queue(queue_url=queue_url)
    except ClientError as error:
        error_code = error.response['Error']['Code']
        error_message = error.response['Error']['Message']
        logger.error("Queue %s is not available. %s: %s", queue_url, error_code, error_message)
        return None

    try:
        verify_certtype(cert_type)
    except ValueError as error:
        logger.error("Certificate type %s did not verify: %s", queue_url, str(error))
        return None

    for record in sqs_event.records:
        config = json.loads(record["body"])
        invoke_export(config, queue_url, cert_type)

    return event

"""
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

Lambda function to decompose Infineon based certificate manifest(s) and begin
the import processing pipeline
"""
import os
import json
import logging
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
    if not verify_queue(queue_url=queue_url):
        logger.error("Queue {queue_url} is not available. ")
        return None

    cert_type = os.environ['CERT_TYPE']
    if not verify_certtype(cert_type):
        logger.error("Certificate type not valid. Must be E0E0, E0E1, or E0E2.")
        return None


    queue_url = os.environ['QUEUE_TARGET']

    for record in sqs_event.records:
        config = json.loads(record["body"])
        invoke_export(config, queue_url, cert_type)

    return event

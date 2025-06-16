"""
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

Lambda function to import Microchip manifest
"""
import os
import json
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.utilities.data_classes import SQSEvent
from .manifest_handler import invoke_export

def lambda_handler(event: SQSEvent, context: LambdaContext) -> dict: # pylint: disable=unused-argument
    """Lambda function main entry point"""
    queue_url = os.environ['QUEUE_TARGET']

    sqs_event = SQSEvent(event)
    for record in sqs_event.records:
        config = json.loads(record["body"])
        invoke_export(config, queue_url)

    return event

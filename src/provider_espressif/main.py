"""
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

Lambda function to decompose Espressif based certificate manifest(s) and begin
the import processing pipeline
"""
import os
import io
import csv
import json
import base64
import logging
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.utilities.data_classes import SQSEvent
from aws_utils import s3_object_bytes, send_sqs_message

logger = logging.getLogger()
logger.setLevel("INFO")

def invoke_export(config: hash, queue_url: str):
    """Evaluate CSV based Espressif manifest"""
    manifest_bytes = s3_object_bytes(config['bucket'],
                                     config['key'],
                                     getvalue=True)
    reader_list = csv.DictReader(io.StringIO(manifest_bytes.decode()))

    for row in reader_list:
        config['thing'] = row['MAC']
        config['certificate'] = str(base64.b64encode(row['cert'].encode('ascii')))
        send_sqs_message(config, queue_url)

def lambda_handler(event: dict, context: LambdaContext) -> dict: # pylint: disable=unused-argument
    """Lambda function main entry point"""
    sqs_event = SQSEvent(event)
    queue_url = os.environ['QUEUE_TARGET']
    if event.get('Records') is None:
        #TODO throw an exception here
        return None
    for record in event['Records']:
        if record.get('eventSource') == 'aws:sqs':
            config = json.loads(record["body"])
            invoke_export(config, queue_url)

    return event

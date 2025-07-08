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
    """
    Process Espressif certificate manifests from SQS messages and forward to target queue.
    
    This Lambda function processes SQS messages containing S3 bucket and object information
    for Espressif certificate manifests. For each manifest:
    1. Retrieves the CSV-formatted certificate manifest from S3
    2. Parses the CSV file containing device certificates and MAC addresses
    3. For each device entry in the CSV:
       a. Uses the device MAC address as the Thing name
       b. Base64 encodes the certificate data
       c. Forwards the certificate data and Thing name to the target SQS queue
    
    The Espressif manifest is expected to be in CSV format with at least two columns:
    - 'MAC': The device MAC address to be used as the Thing name
    - 'cert': The PEM-formatted device certificate
    
    Environment variables:
        QUEUE_TARGET: URL of the SQS queue to forward processed certificates to
    
    Args:
        event (dict): SQS event containing messages with S3 bucket/object information
        context (LambdaContext): Lambda execution context (unused)
        
    Returns:
        dict: The original event for AWS Lambda SQS batch processing
    """
    sqs_event = SQSEvent(event)
    queue_url = os.environ['QUEUE_TARGET']

    for record in sqs_event.records:
        config = json.loads(record["body"])
        invoke_export(config, queue_url)

    return event

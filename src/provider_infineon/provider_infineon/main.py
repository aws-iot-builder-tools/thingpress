"""
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

Lambda function to decompose Infineon based certificate manifest(s) and begin
the import processing pipeline
"""
import json
import os
import sys

from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.idempotency.config import IdempotencyConfig
from aws_lambda_powertools.utilities.idempotency.persistence.dynamodb import \
    DynamoDBPersistenceLayer
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.utilities.data_classes import SQSEvent
from boto3 import Session
from botocore.exceptions import ClientError
from layer_utils.aws_utils import boto_exception, verify_queue, powertools_idempotency_environ
from provider_infineon.manifest_handler import invoke_export, verify_certtype

# Initialize Logger and Idempotency
logger = Logger(service="provider_infineon")
default_session: Session = Session()

persistence_layer, idempotency_config = powertools_idempotency_environ()

def file_key_generator(event, _context):
    """Generate a unique key based on S3 bucket and key"""
    if isinstance(event, dict) and "bucket" in event and "key" in event:
        # Use bucket and key as the idempotency key
        return f"{event['bucket']}:{event['key']}"
    return None

#@idempotent_function(
#    persistence_store=persistence_layer,
#    config=idempotency_config,
#    event_key_generator=file_key_generator,
#    data_keyword_argument="config"
#)
def process_infineon_manifest(config, queue_url, cert_type, session=default_session):
    """Process Infineon manifest with idempotency"""
    logger.info({
        "message": "Processing Infineon manifest",
        "bucket": config['bucket'],
        "key": config['key'],
        "cert_type": cert_type
    })

    count = invoke_export(config, queue_url, cert_type, session)

    logger.info({
        "message": "Processed certificates from Infineon manifest",
        "count": count,
        "bucket": config['bucket'],
        "key": config['key']
    })

    return count

def lambda_handler(event: dict, context: LambdaContext) -> dict: # pylint: disable=unused-argument
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
        POWERTOOLS_IDEMPOTENCY_TABLE: DynamoDB table for idempotency
        POWERTOOLS_IDEMPOTENCY_EXPIRY_SECONDS: Expiry time for idempotency records
    
    Args:
        event (dict): SQS event containing messages with S3 bucket/object information
        context (LambdaContext): Lambda execution context (unused)
        
    Returns:
        dict: The original event for AWS Lambda SQS batch processing, or None if validation fails
    """
    # Convert raw dict to SQSEvent (AWS always sends raw dict to Lambda handlers)
    sqs_event = SQSEvent(event)

    queue_url = os.environ['QUEUE_TARGET']
    cert_type = os.environ['CERT_TYPE']
    total_processed = 0

    try:
        verify_queue(queue_url=queue_url, session=default_session)
    except ClientError as exc:
        boto_exception(exc, f"Queue {queue_url} is not available")
        raise exc

    try:
        verify_certtype(cert_type)
    except ValueError as error:
        # TODO write a general exception logging mechanism for not boto calls, and have the boto exception code call that
        logger.error({
            "message": "Certificate type verification failed",
            "cert_type": cert_type,
            "error": str(error)
        })
        raise error

    for record in sqs_event.records:
        config = json.loads(record.body)
        logger.info({
            "message": "Processing SQS message",
            "bucket": config.get('bucket'),
            "key": config.get('key')
        })
        total_processed += process_infineon_manifest(config, queue_url, cert_type)

    logger.info({
        "message": "Total certificates processed",
        "count": total_processed
    })

    return event

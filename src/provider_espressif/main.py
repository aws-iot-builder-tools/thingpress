"""
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

Lambda function to decompose Espressif based certificate manifest(s) and begin
the import processing pipeline
"""
import os
from io import StringIO
import csv
import json
import base64
from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.utilities.data_classes import SQSEvent
from aws_lambda_powertools.utilities.idempotency import idempotent_function
from aws_lambda_powertools.utilities.idempotency.persistence.dynamodb import (
    DynamoDBPersistenceLayer)
from aws_lambda_powertools.utilities.idempotency.config import IdempotencyConfig
from layer_utils.aws_utils import s3_object_bytes
from layer_utils.throttling_utils import create_standardized_throttler
from boto3 import Session

# Initialize Logger and Idempotency
logger = Logger(service="provider_espressif")
default_session: Session = Session()

if os.environ.get("POWERTOOLS_IDEMPOTENCY_TABLE") is None:
    raise ValueError("Environment variable POWERTOOLS_IDEMPOTENCY_TABLE not set.")
POWERTOOLS_IDEMPOTENCY_TABLE: str = os.environ["POWERTOOLS_IDEMPOTENCY_TABLE"]
if os.environ.get("POWERTOOLS_IDEMPOTENCY_EXPIRY_SECONDS") is None:
    POWERTOOLS_IDEMPOTENCY_EXPIRY_SECONDS: int = 3600
POWERTOOLS_IDEMPOTENCY_EXPIRY_SECONDS: int = int(
    os.environ.get("POWERTOOLS_IDEMPOTENCY_EXPIRY_SECONDS", 3600))

# Initialize persistence layer for idempotency
persistence_layer = DynamoDBPersistenceLayer(
    table_name=POWERTOOLS_IDEMPOTENCY_TABLE,
    key_attr="id",
    expiry_attr="expiration",
    status_attr="status",
    data_attr="data",
    validation_key_attr="validation"
)

# Configure idempotency
idempotency_config = IdempotencyConfig(
    expires_after_seconds=POWERTOOLS_IDEMPOTENCY_EXPIRY_SECONDS
)

def file_key_generator(event, context):
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
def invoke_export(config: dict, queue_url: str, session: Session=default_session):
    """Evaluate CSV based Espressif manifest"""
    logger.info({
        "message": "Processing Espressif manifest",
        "bucket": config['bucket'],
        "key": config['key']
    })

    manifest_bytes = s3_object_bytes(config['bucket'],
                                     config['key'],
                                     getvalue=True,
                                     session=session)
    reader_list = csv.DictReader(StringIO(manifest_bytes.decode()))

    # Process certificates in batches for optimal SQS throughput
    batch_messages = []
    batch_size = 10  # SQS batch limit
    total_count = 0
    
    # Initialize standardized throttler
    throttler = create_standardized_throttler()
    
    for row in reader_list:
        cert_config = config.copy()
        cert_config['thing'] = row['MAC']
        cert_config['certificate'] = base64.b64encode(row['cert'].encode('ascii')).decode('ascii')
        
        batch_messages.append(cert_config)
        total_count += 1
        
        # Send batch when full
        if len(batch_messages) >= batch_size:
            throttler.send_batch_with_throttling(batch_messages, queue_url, session)
            batch_messages = []
    
    # Send remaining messages
    if batch_messages:
        throttler.send_batch_with_throttling(batch_messages, queue_url, session, is_final_batch=True)

    # Get throttling statistics for logging
    throttling_stats = throttler.get_throttling_stats()
    
    logger.info({
        "message": "Processed certificates from Espressif manifest with standardized throttling",
        "total_certificates": total_count,
        "total_batches": throttling_stats["total_batches_processed"],
        "api_calls_saved": total_count - throttling_stats["total_batches_processed"],
        "throttling_stats": throttling_stats,
        "bucket": config['bucket'],
        "key": config['key']
    })

    return total_count

def lambda_handler(event, context: LambdaContext) -> dict: # pylint: disable=unused-argument
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
        POWERTOOLS_IDEMPOTENCY_TABLE: DynamoDB table for idempotency
        POWERTOOLS_IDEMPOTENCY_EXPIRY_SECONDS: Expiry time for idempotency records
    
    Args:
        event (dict): SQS event containing messages with S3 bucket/object information
        context (LambdaContext): Lambda execution context (unused)
        
    Returns:
        dict: The original event for AWS Lambda SQS batch processing
    """
    # Handle both raw dict and SQSEvent object formats
    if hasattr(event, 'records'):
        # SQSEvent object format
        sqs_event = event
        raw_event = event.raw_event
    else:
        # Raw dict format - convert to SQSEvent
        from aws_lambda_powertools.utilities.data_classes import SQSEvent
        sqs_event = SQSEvent(event)
        raw_event = event
    
    queue_url = os.environ['QUEUE_TARGET']
    total_processed = 0

    for record in sqs_event.records:
        config = json.loads(record.body)
        logger.info({
            "message": "Processing SQS message",
            "bucket": config.get('bucket'),
            "key": config.get('key')
        })
        total_processed += invoke_export(config=config,
                                         queue_url=queue_url,
                                         session=default_session)

    logger.info({
        "message": "Total certificates processed",
        "count": total_processed
    })

    return raw_event

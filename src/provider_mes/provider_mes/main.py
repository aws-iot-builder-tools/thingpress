# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""
MES Provider Lambda
Processes device-infos JSON files and sends messages to Bulk Importer queue.
Supports Phase 2 of two-phase provisioning (device activation with metadata).

This provider follows the same pattern as other providers (Espressif, Infineon, etc.):
- Receives SQS events from Product Verifier
- Processes device-infos JSON files from S3
- Sends messages to Bulk Importer queue with throttling
"""
import json
import os
import re

from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.utilities.data_classes import SQSEvent
from aws_lambda_powertools.utilities.idempotency import idempotent_function
from boto3 import Session

# Layer utilities
from layer_utils.aws_utils import (
    s3_object_bytes,
    powertools_idempotency_environ,
    ProviderMessageKey
)
from layer_utils.throttling_utils import create_standardized_throttler
from layer_utils.status_utils import write_device_queued, write_device_failed

# Initialize Logger and Idempotency
logger = Logger(service="provider_mes")
default_session: Session = Session()

persistence_layer, idempotency_config = powertools_idempotency_environ()


def file_key_generator(event, _context):
    """Generate a unique key based on S3 bucket and key"""
    if isinstance(event, dict) and "bucket" in event and "key" in event:
        return f"{event[ProviderMessageKey.OBJECT_BUCKET.value]}:" \
               f"{event[ProviderMessageKey.OBJECT_KEY.value]}"
    return None


def validate_device_infos(data: dict) -> None:
    """
    Validate device-infos JSON structure.

    Expected format:
    {
        "batchId": "batch-001",
        "devices": [
            {
                "certFingerprint": "a1b2c3...",
                "deviceId": "device-001",
                "deviceType": "MyDeviceType",
                "attributes": {
                    "DSN": "DSN123",
                    "MAC": "AA:BB:CC:DD:EE:FF"
                }
            }
        ]
    }

    Raises:
        ValueError: If structure is invalid
    """
    if 'batchId' not in data:
        raise ValueError("Missing required field: batchId")

    if 'devices' not in data or not data['devices']:
        raise ValueError("Missing or empty devices array")

    for idx, device in enumerate(data['devices']):
        if 'certFingerprint' not in device:
            raise ValueError(f"Device {idx}: Missing certFingerprint")

        fingerprint = device['certFingerprint']
        if not isinstance(fingerprint, str) or len(fingerprint) != 64:
            raise ValueError(f"Device {idx}: Invalid certFingerprint format (must be 64 hex chars)")

        # Validate hex characters
        if not re.match(r'^[a-fA-F0-9]{64}$', fingerprint):
            raise ValueError(
                f"Device {idx}: certFingerprint must contain only hex characters "
                f"(0-9, a-f, A-F)"
            )

        if 'deviceId' not in device:
            raise ValueError(f"Device {idx}: Missing deviceId")


def build_bulk_importer_message(device: dict, config: dict, batch_id: str) -> dict:
    """
    Build message for Bulk Importer queue.

    Args:
        device: Device info from device-infos JSON
        config: Configuration from Product Verifier (policies, thing_groups, cert_active, etc.)
        batch_id: Batch identifier to include in the message for DynamoDB status tracking

    Returns:
        Message dict for Bulk Importer
    """
    message = {
        'certificate': device['certFingerprint'].lower(),
        'thing': device['deviceId'],
        'cert_format': 'FINGERPRINT',
        'thing_deferred': 'FALSE',  # MES always creates Things (Phase 2)
        'policies': config.get('policies', []),
        'thing_groups': config.get('thing_groups', []),
        'batch_id': batch_id,
    }

    # Pass through cert_active from Product Verifier config
    # This determines if certificate should be ACTIVE or PENDING_ACTIVATION
    if 'cert_active' in config:
        message['cert_active'] = config['cert_active']

    # Add thing type: device-level deviceType overrides config-level thing_type_name
    device_type = device.get('deviceType')
    if device_type:
        message['thing_type_name'] = device_type
    elif 'thing_type_name' in config:
        message['thing_type_name'] = config['thing_type_name']

    # Add attributes if present
    if 'attributes' in device and device['attributes']:
        message['attributes'] = device['attributes']

    return message


@idempotent_function(
    persistence_store=persistence_layer,
    config=idempotency_config,
    data_keyword_argument="config"
)
def process_device_infos_file(
        config: dict,
        queue_url: str,
        session: Session = default_session,
        status_table: str = None) -> int:
    """
    Process device-infos JSON file from S3.

    Args:
        config: Configuration from Product Verifier (bucket, key, policies, thing_groups)
        queue_url: URL of the Bulk Importer queue
        session: boto3 Session
        status_table: DynamoDB table name for device status tracking (None to skip writes)

    Returns:
        int: Number of devices processed
    """
    bucket = config.get(ProviderMessageKey.OBJECT_BUCKET.value)
    key = config.get(ProviderMessageKey.OBJECT_KEY.value)

    if not bucket or not key:
        raise ValueError("Missing required config fields: bucket or key")

    logger.info({
        "message": "Processing device-infos file",
        "bucket": bucket,
        "key": key
    })

    # Download and parse JSON
    file_bytes = s3_object_bytes(bucket, key, session)
    data = json.loads(file_bytes.decode('utf-8'))

    # Validate structure
    validate_device_infos(data)

    logger.info({
        "message": "Device-infos file validated",
        "batch_id": data['batchId'],
        "device_count": len(data['devices'])
    })

    # Process devices in batches for optimal SQS throughput
    batch_messages = []
    batch_size = 10  # SQS batch limit
    count = 0
    batch_id = data['batchId']

    # Initialize standardized throttler
    throttler = create_standardized_throttler()

    for device in data['devices']:
        try:
            message = build_bulk_importer_message(device, config, batch_id)
            batch_messages.append(message)
            count += 1

            # Write QUEUED status to DynamoDB (fire-and-forget)
            write_device_queued(status_table, batch_id, device['deviceId'],
                                device['certFingerprint'].lower(), session)

        except Exception as e:  # pylint: disable=broad-except
            logger.error({
                "message": "Error processing device",
                "device_id": device.get('deviceId', 'unknown'),
                "error_code": type(e).__name__,
                "error": str(e)
            })
            # Write FAILED status to DynamoDB (fire-and-forget)
            write_device_failed(status_table, batch_id,
                                device.get('deviceId', 'unknown'),
                                device.get('certFingerprint', 'unknown').lower(),
                                type(e).__name__, str(e), session)
            # Continue processing other devices (fail-independently)
            continue

        # Send batch when full (outside per-device try/except so SQS errors propagate)
        if len(batch_messages) >= batch_size:
            try:
                throttler.send_batch_with_throttling(
                    batch_messages, queue_url, session)
            except Exception as sqs_err:
                # Mark all devices in this batch as FAILED
                for msg in batch_messages:
                    write_device_failed(
                        status_table, batch_id,
                        msg.get('thing', 'unknown'),
                        msg.get('certificate', 'unknown'),
                        type(sqs_err).__name__, str(sqs_err), session)
                raise
            batch_messages = []

    # Send remaining messages in final batch
    if batch_messages:
        try:
            throttler.send_batch_with_throttling(
                batch_messages, queue_url, session, is_final_batch=True)
        except Exception as sqs_err:
            # Mark all devices in this final batch as FAILED
            for msg in batch_messages:
                write_device_failed(
                    status_table, batch_id,
                    msg.get('thing', 'unknown'),
                    msg.get('certificate', 'unknown'),
                    type(sqs_err).__name__, str(sqs_err), session)
            raise

    # Get throttling statistics for logging
    throttling_stats = throttler.get_throttling_stats()

    logger.info({
        "message": "Processed devices from MES manifest with standardized throttling",
        "batch_id": data['batchId'],
        "total_devices": count,
        "total_batches": throttling_stats["total_batches_processed"],
        "api_calls_saved": count - int(throttling_stats["total_batches_processed"]),
        "throttling_stats": throttling_stats,
        "bucket": bucket,
        "key": key
    })

    return count


def lambda_handler(event: dict, context: LambdaContext) -> dict: # pylint: disable=unused-argument
    """
    Process MES device-infos files from SQS messages and forward to Bulk Importer queue.

    This Lambda function processes SQS messages from Product Verifier containing S3 bucket
    and object information for MES device-infos JSON files. For each file:
    1. Retrieves the JSON file from S3
    2. Validates the structure (batchId, devices array)
    3. For each device in the file:
       a. Extracts certificate fingerprint and device ID
       b. Builds message with FINGERPRINT format
       c. Uses device-level deviceType as thing type if present
       d. Includes device attributes if present
       e. Forwards to Bulk Importer queue with throttling

    The device-infos files are expected to be in JSON format with structure:
    {
        "batchId": "batch-001",
        "devices": [
            {
                "certFingerprint": "64-char-hex-string",
                "deviceId": "device-001",
                "deviceType": "MyDeviceType",
                "attributes": {"DSN": "...", "MAC": "..."}
            }
        ]
    }

    Environment variables:
        QUEUE_TARGET: URL of the Bulk Importer SQS queue
        DEVICE_STATUS_TABLE: DynamoDB table name for device status tracking (optional)
        POWERTOOLS_IDEMPOTENCY_TABLE: DynamoDB table for idempotency
        POWERTOOLS_IDEMPOTENCY_EXPIRY_SECONDS: Expiry time for idempotency records
        AUTO_THROTTLING_ENABLED: Enable/disable adaptive throttling
        THROTTLING_BASE_DELAY: Base delay for throttling
        THROTTLING_BATCH_INTERVAL: Interval between batches
        MAX_QUEUE_DEPTH: Maximum queue depth threshold

    Args:
        event (dict): SQS event containing messages from Product Verifier
        context (LambdaContext): Lambda execution context

    Returns:
        dict: The original event for AWS Lambda SQS batch processing
    """
    # Convert raw dict to SQSEvent
    sqs_event = SQSEvent(event)

    queue_url = os.environ['QUEUE_TARGET']
    status_table = os.environ.get('DEVICE_STATUS_TABLE') or None

    total_processed = 0

    for record in sqs_event.records:
        config = json.loads(record.body)
        logger.info({
            "message": "Processing SQS message",
            "bucket": config.get('bucket'),
            "key": config.get('key')
        })

        result = process_device_infos_file(
            config=config,
            queue_url=queue_url,
            session=default_session,
            status_table=status_table
        )

        total_processed += result

    logger.info({
        "message": "Total devices processed",
        "count": total_processed
    })

    return event

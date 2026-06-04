# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""DynamoDB device status tracking utilities.

All functions catch exceptions, log them, and never raise — DynamoDB writes
must not break the main processing pipeline. If the table name is None or
empty the function returns immediately (backward compatible).
"""

from datetime import datetime, timezone

from aws_lambda_powertools import Logger
from boto3 import Session

logger = Logger(child=True)

VENDOR = "mes"


def _now_iso() -> str:
    """Return current UTC time as ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


def write_device_queued(table, batch_id, device_id, fingerprint, session):
    """Write a QUEUED status record for a device via PutItem.

    Args:
        table: DynamoDB table name (None/empty to skip)
        batch_id: Batch identifier
        device_id: Device identifier (Thing name)
        fingerprint: Certificate SHA-256 fingerprint
        session: boto3 Session
    """
    if not table:
        return
    try:
        dynamodb = session.resource("dynamodb")
        ddb_table = dynamodb.Table(table)
        ddb_table.put_item(Item={
            "batch_id": batch_id,
            "device_id": device_id,
            "cert_fingerprint": fingerprint,
            "status": "QUEUED",
            "queued_at": _now_iso(),
            "vendor": VENDOR,
        })
    except Exception:
        logger.exception("Failed to write QUEUED status for device %s in batch %s",
                         device_id, batch_id)


def write_device_failed(table, batch_id, device_id, fingerprint,
                        error_code, error_msg, session):
    """Write a FAILED status record for a device via PutItem.

    Used when a device fails during the provider phase (validation, queueing).

    Args:
        table: DynamoDB table name (None/empty to skip)
        batch_id: Batch identifier
        device_id: Device identifier (Thing name)
        fingerprint: Certificate SHA-256 fingerprint
        error_code: Error code string
        error_msg: Human-readable error detail
        session: boto3 Session
    """
    if not table:
        return
    try:
        now = _now_iso()
        dynamodb = session.resource("dynamodb")
        ddb_table = dynamodb.Table(table)
        ddb_table.put_item(Item={
            "batch_id": batch_id,
            "device_id": device_id,
            "cert_fingerprint": fingerprint,
            "status": "FAILED",
            "queued_at": now,
            "completed_at": now,
            "error_code": error_code,
            "error_message": error_msg,
            "vendor": VENDOR,
        })
    except Exception:
        logger.exception("Failed to write FAILED status for device %s in batch %s",
                         device_id, batch_id)


def update_device_succeeded(table, batch_id, device_id, session):
    """Update an existing device record to SUCCEEDED via UpdateItem.

    Only updates if the record already exists (ConditionExpression).

    Args:
        table: DynamoDB table name (None/empty to skip)
        batch_id: Batch identifier
        device_id: Device identifier (Thing name)
        session: boto3 Session
    """
    if not table:
        return
    try:
        dynamodb = session.resource("dynamodb")
        ddb_table = dynamodb.Table(table)
        ddb_table.update_item(
            Key={"batch_id": batch_id, "device_id": device_id},
            UpdateExpression="SET #s = :status, completed_at = :completed_at",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={
                ":status": "SUCCEEDED",
                ":completed_at": _now_iso(),
            },
            ConditionExpression="attribute_exists(batch_id)",
        )
    except Exception:
        logger.exception("Failed to update SUCCEEDED status for device %s in batch %s",
                         device_id, batch_id)


def update_device_failed(table, batch_id, device_id,
                         error_code, error_msg, session):
    """Update an existing device record to FAILED via UpdateItem.

    Used by the bulk importer when IoT operations fail for a device.
    Only updates if the record already exists (ConditionExpression).

    Args:
        table: DynamoDB table name (None/empty to skip)
        batch_id: Batch identifier
        device_id: Device identifier (Thing name)
        error_code: Error code string
        error_msg: Human-readable error detail
        session: boto3 Session
    """
    if not table:
        return
    try:
        dynamodb = session.resource("dynamodb")
        ddb_table = dynamodb.Table(table)
        ddb_table.update_item(
            Key={"batch_id": batch_id, "device_id": device_id},
            UpdateExpression=(
                "SET #s = :status, completed_at = :completed_at, "
                "error_code = :error_code, "
                "error_message = :error_message"
            ),
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={
                ":status": "FAILED",
                ":completed_at": _now_iso(),
                ":error_code": error_code,
                ":error_message": error_msg,
            },
            ConditionExpression="attribute_exists(batch_id)",
        )
    except Exception:
        logger.exception("Failed to update FAILED status for device %s in batch %s",
                         device_id, batch_id)

# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""
Unit tests for layer_utils.status_utils

Tests the fire-and-forget DynamoDB device status tracking utilities.
"""

import os
import logging
from unittest import TestCase
from unittest.mock import patch, MagicMock

from boto3 import _get_default_session
from moto import mock_aws

# Disable logging to stdout during tests
logging.getLogger().setLevel(logging.CRITICAL)
for log_name in ['boto3', 'botocore', 'urllib3', 'moto', 'aws_lambda_powertools']:
    logging.getLogger(log_name).setLevel(logging.CRITICAL)
    logging.getLogger(log_name).propagate = False

# Ensure that we are not using real AWS credentials
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
os.environ["AWS_REGION"] = "us-east-1"
os.environ["AWS_ACCESS_KEY_ID"] = "testing"
os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
os.environ["AWS_SECURITY_TOKEN"] = "testing"
os.environ["AWS_SESSION_TOKEN"] = "testing"
os.environ["POWERTOOLS_LOG_LEVEL"] = "CRITICAL"

from layer_utils.status_utils import (
    write_device_queued,
    write_device_failed,
    update_device_succeeded,
    update_device_failed,
)

TABLE_NAME = "test-device-status-table"


@mock_aws(config={
    "core": {
        "mock_credentials": True,
        "reset_boto3_session": True,
        "service_whitelist": None,
    }})
class TestStatusUtils(TestCase):
    """Unit tests for status_utils functions with mocked DynamoDB."""

    def setUp(self):
        """Create a mocked DynamoDB table for tests."""
        self.session = _get_default_session()
        dynamodb = self.session.client("dynamodb")
        dynamodb.create_table(
            TableName=TABLE_NAME,
            KeySchema=[
                {"AttributeName": "batch_id", "KeyType": "HASH"},
                {"AttributeName": "device_id", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "batch_id", "AttributeType": "S"},
                {"AttributeName": "device_id", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )

    def tearDown(self):
        """Delete the mocked DynamoDB table."""
        dynamodb = self.session.client("dynamodb")
        try:
            dynamodb.delete_table(TableName=TABLE_NAME)
        except Exception:
            pass

    # ========================================================================
    # 6.1 — write_device_queued
    # ========================================================================

    def test_write_device_queued_creates_correct_item(self):
        """write_device_queued creates a QUEUED item with expected attributes."""
        write_device_queued(TABLE_NAME, "batch-1", "dev-1", "aabb" * 16, self.session)

        table = self.session.resource("dynamodb").Table(TABLE_NAME)
        resp = table.get_item(Key={"batch_id": "batch-1", "device_id": "dev-1"})
        item = resp["Item"]

        self.assertEqual(item["status"], "QUEUED")
        self.assertEqual(item["cert_fingerprint"], "aabb" * 16)
        self.assertEqual(item["vendor"], "mes")
        self.assertIn("queued_at", item)
        # QUEUED items should NOT have completed_at or error fields
        self.assertNotIn("completed_at", item)
        self.assertNotIn("error_code", item)

    # ========================================================================
    # 6.1 — write_device_failed
    # ========================================================================

    def test_write_device_failed_creates_correct_item(self):
        """write_device_failed creates a FAILED item with error fields."""
        write_device_failed(
            TABLE_NAME, "batch-2", "dev-2", "ccdd" * 16,
            "MISSING_CERT", "cert not found", self.session,
        )

        table = self.session.resource("dynamodb").Table(TABLE_NAME)
        resp = table.get_item(Key={"batch_id": "batch-2", "device_id": "dev-2"})
        item = resp["Item"]

        self.assertEqual(item["status"], "FAILED")
        self.assertEqual(item["error_code"], "MISSING_CERT")
        self.assertEqual(item["error_message"], "cert not found")
        self.assertIn("queued_at", item)
        self.assertIn("completed_at", item)

    # ========================================================================
    # 6.1 — update_device_succeeded
    # ========================================================================

    def test_update_device_succeeded_updates_status(self):
        """update_device_succeeded sets status to SUCCEEDED and adds completed_at."""
        # Seed a QUEUED record first
        write_device_queued(TABLE_NAME, "batch-3", "dev-3", "eeff" * 16, self.session)

        update_device_succeeded(TABLE_NAME, "batch-3", "dev-3", self.session)

        table = self.session.resource("dynamodb").Table(TABLE_NAME)
        resp = table.get_item(Key={"batch_id": "batch-3", "device_id": "dev-3"})
        item = resp["Item"]

        self.assertEqual(item["status"], "SUCCEEDED")
        self.assertIn("completed_at", item)

    # ========================================================================
    # 6.1 — update_device_failed
    # ========================================================================

    def test_update_device_failed_updates_status_with_error_fields(self):
        """update_device_failed sets status to FAILED with error details."""
        # Seed a QUEUED record first
        write_device_queued(TABLE_NAME, "batch-4", "dev-4", "1122" * 16, self.session)

        update_device_failed(
            TABLE_NAME, "batch-4", "dev-4",
            "PROVISIONING_FAILED", "IoT error", self.session,
        )

        table = self.session.resource("dynamodb").Table(TABLE_NAME)
        resp = table.get_item(Key={"batch_id": "batch-4", "device_id": "dev-4"})
        item = resp["Item"]

        self.assertEqual(item["status"], "FAILED")
        self.assertEqual(item["error_code"], "PROVISIONING_FAILED")
        self.assertEqual(item["error_message"], "IoT error")
        self.assertIn("completed_at", item)

    # ========================================================================
    # 6.2 — Graceful degradation: table=None / empty
    # ========================================================================

    def test_write_device_queued_skips_when_table_none(self):
        """write_device_queued returns early when table is None."""
        # Should not raise and should not touch DynamoDB
        write_device_queued(None, "b", "d", "fp", self.session)

    def test_write_device_queued_skips_when_table_empty(self):
        """write_device_queued returns early when table is empty string."""
        write_device_queued("", "b", "d", "fp", self.session)

    def test_write_device_failed_skips_when_table_none(self):
        """write_device_failed returns early when table is None."""
        write_device_failed(None, "b", "d", "fp", "c", "m", self.session)

    def test_update_device_succeeded_skips_when_table_none(self):
        """update_device_succeeded returns early when table is None."""
        update_device_succeeded(None, "b", "d", self.session)

    def test_update_device_failed_skips_when_table_none(self):
        """update_device_failed returns early when table is None."""
        update_device_failed(None, "b", "d", "c", "m", self.session)

    # ========================================================================
    # 6.2 — Graceful degradation: DynamoDB exception doesn't propagate
    # ========================================================================

    def test_write_device_queued_swallows_dynamodb_exception(self):
        """DynamoDB exception in write_device_queued is caught and logged, not raised."""
        mock_session = MagicMock()
        mock_table = MagicMock()
        mock_session.resource.return_value.Table.return_value = mock_table
        mock_table.put_item.side_effect = Exception("DynamoDB boom")

        # Should NOT raise
        write_device_queued(TABLE_NAME, "b", "d", "fp", mock_session)

    def test_write_device_failed_swallows_dynamodb_exception(self):
        """DynamoDB exception in write_device_failed is caught and logged, not raised."""
        mock_session = MagicMock()
        mock_table = MagicMock()
        mock_session.resource.return_value.Table.return_value = mock_table
        mock_table.put_item.side_effect = Exception("DynamoDB boom")

        write_device_failed(TABLE_NAME, "b", "d", "fp", "c", "m", mock_session)

    def test_update_device_succeeded_swallows_dynamodb_exception(self):
        """DynamoDB exception in update_device_succeeded is caught and logged, not raised."""
        mock_session = MagicMock()
        mock_table = MagicMock()
        mock_session.resource.return_value.Table.return_value = mock_table
        mock_table.update_item.side_effect = Exception("DynamoDB boom")

        update_device_succeeded(TABLE_NAME, "b", "d", mock_session)

    def test_update_device_failed_swallows_dynamodb_exception(self):
        """DynamoDB exception in update_device_failed is caught and logged, not raised."""
        mock_session = MagicMock()
        mock_table = MagicMock()
        mock_session.resource.return_value.Table.return_value = mock_table
        mock_table.update_item.side_effect = Exception("DynamoDB boom")

        update_device_failed(TABLE_NAME, "b", "d", "c", "m", mock_session)

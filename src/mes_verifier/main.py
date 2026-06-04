# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""MES Verifier Function (S3 Event Handler)

This function handles S3 events from the MES manifest bucket and routes them to
the MES Provider queue. It's specifically designed for Manufacturing Execution
System (MES) two-phase provisioning workflows.

Event Flow:
S3 Upload (MES Bucket) → MES Verifier (S3 Event) → SQS Queue → MES Provider
(SQS Event) → Bulk Importer

Key Differences from Product Verifier:
- Only handles MES manifests (device-infos JSON files)
- Hardcoded to FINGERPRINT format (Phase 2 behavior)
- Always creates Things (thing_deferred=FALSE)
- Always activates certificates (cert_active=TRUE)
- No environment variable configuration needed for cert format
"""
import logging
import os

from aws_lambda_powertools.utilities.data_classes import S3Event
from aws_lambda_powertools.utilities.typing import LambdaContext
from boto3 import Session
from layer_utils.aws_utils import (check_cfn_prop_valid, get_policy_arn, get_thing_group_arn,
                                   get_thing_type_arn, send_sqs_message)

logger = logging.getLogger()
logger.setLevel("INFO")

default_session: Session = Session()

def parse_comma_delimited_list(value: str) -> list[str]:
    """Parse comma-delimited string into list, filtering out 'None' and empty
    values"""
    if not value or value.strip().lower() == 'none':
        return []
    return [item.strip() for item in value.split(',')
            if item.strip() and item.strip().lower() != 'none']


def lambda_handler(event,
                   context: LambdaContext) -> dict: # pylint: disable=unused-argument
    """Lambda function main entry point for MES manifest processing.
    
    Verifies the S3 object can be read and resolves inputs prior to forwarding
    to MES Provider queue. This function is specifically designed for MES
    two-phase provisioning and always uses FINGERPRINT format.

    This lambda function expects invocation by S3 event from the MES manifest
    bucket. There should be only one event, but is processed as if multiple
    events were found.

    Expects the following environment variables to be set:
    QUEUE_TARGET_MES: URL of the MES Provider SQS queue
    POLICY_NAMES: Comma-delimited list of IoT policy names (optional)
    THING_GROUP_NAMES: Comma-delimited list of IoT thing group names (optional)
    THING_TYPE_NAME: IoT thing type name (optional)
    """
    # Get environment variables
    e_policies = os.environ.get('POLICY_NAMES', '')
    e_thing_groups = os.environ.get('THING_GROUP_NAMES', '')
    e_thing_type = os.environ.get('THING_TYPE_NAME', '')
    queue_url = os.environ['QUEUE_TARGET_MES']

    # Handle both raw dict and S3Event object formats
    if hasattr(event, 'records'):
        s3_event = event
        raw_event = event.raw_event
    else:
        s3_event = S3Event(event)
        raw_event = event

    # Process the first record to get bucket name
    records_list = list(s3_event.records)
    first_record = records_list[0]
    bucket_name = first_record.s3.bucket.name

    # Build configuration
    config = _build_config(
        bucket_name, e_policies, e_thing_groups, e_thing_type
    )

    # Send messages for each record
    for record in records_list:
        config['key'] = record.s3.get_object.key
        logger.info("Processing MES device-infos manifest: %s",
                    record.s3.get_object.key)
        send_sqs_message(config, queue_url, default_session)
        logger.info("Sent message to MES Provider queue %s for s3://%s/%s",
                    queue_url, bucket_name, record.s3.get_object.key)

    return raw_event


def _build_config(bucket_name: str, e_policies: str, e_thing_groups: str,
                  e_thing_type: str) -> dict:
    """Build configuration dictionary for MES processing.
    
    Args:
        bucket_name: S3 bucket name
        e_policies: Comma-delimited policy names
        e_thing_groups: Comma-delimited thing group names
        e_thing_type: Thing type name
        
    Returns:
        Configuration dictionary
    """
    config = {'bucket': bucket_name}

    # Parse and validate policies
    policy_names = parse_comma_delimited_list(e_policies)
    if policy_names:
        policies = []
        for policy_name in policy_names:
            if check_cfn_prop_valid(policy_name):
                policy_arn = get_policy_arn(policy_name, default_session)
                policies.append({'name': policy_name, 'arn': policy_arn})
        if policies:
            config['policies'] = policies

    # Parse and validate thing groups
    thing_group_names = parse_comma_delimited_list(e_thing_groups)
    if thing_group_names:
        thing_groups = []
        for thing_group_name in thing_group_names:
            if check_cfn_prop_valid(thing_group_name):
                thing_group_arn = get_thing_group_arn(
                    thing_group_name, default_session
                )
                thing_groups.append({
                    'name': thing_group_name,
                    'arn': thing_group_arn
                })
        if thing_groups:
            config['thing_groups'] = thing_groups

    # Parse and validate thing type
    if e_thing_type and check_cfn_prop_valid(e_thing_type):
        get_thing_type_arn(e_thing_type, default_session)
        config['thing_type_name'] = e_thing_type

    # MES-specific configuration (hardcoded for Phase 2 behavior)
    # These settings are NOT configurable via environment variables
    config['cert_active'] = 'TRUE'        # Always activate certificates
    config['cert_format'] = 'FINGERPRINT' # Always use fingerprint lookup
    config['thing_deferred'] = 'FALSE'    # Always create things with metadata

    return config

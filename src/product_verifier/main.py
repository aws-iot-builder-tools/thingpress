# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""Product Verifier Function (S3 Event Handler)

This function handles S3 events and routes manifests to appropriate SQS queues.
It verifies S3 uploads and does NOT process certificates directly - that's done by
vendor-specific providers.

Event Flow:
S3 Upload → Product Verifier (S3 Event) → SQS Queue → Vendor Provider (SQS Event) → Bulk Importer
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
    """Parse comma-delimited string into list, filtering out 'None' and empty values"""
    if not value or value.strip().lower() == 'none':
        return []
    return [item.strip() for item in value.split(',') 
            if item.strip() and item.strip().lower() != 'none']

ESPRESSIF_BUCKET_PREFIX = "thingpress-espressif-"
INFINEON_BUCKET_PREFIX = "thingpress-infineon-"
MICROCHIP_BUCKET_PREFIX = "thingpress-microchip-"
GENERATED_BUCKET_PREFIX = "thingpress-generated-"

def get_provider_queue(bucket_name: str) -> str:
    """Returns the queue related to the prefix of a given bucket
    The cfn stack prescribes the environment variable value.
    See the cfn template for more detail.
    """
    if bucket_name.startswith(ESPRESSIF_BUCKET_PREFIX):
        return os.environ['QUEUE_TARGET_ESPRESSIF']
    if bucket_name.startswith(INFINEON_BUCKET_PREFIX):
        return os.environ['QUEUE_TARGET_INFINEON']
    if bucket_name.startswith(MICROCHIP_BUCKET_PREFIX):
        return os.environ['QUEUE_TARGET_MICROCHIP']
    if bucket_name.startswith(GENERATED_BUCKET_PREFIX):
        return os.environ['QUEUE_TARGET_GENERATED']
    raise ValueError(f"Bucket name prefix unidentifiable: {bucket_name}")

def lambda_handler(event,
                   context: LambdaContext) -> dict: # pylint: disable=unused-argument
    """Lambda function main entry point. Verifies the S3 object can be read and resolves
    inputs prior to forwarding to vendor handler queue.

    This lambda function expects invocation by S3 event. There should be only one
    event, but is processed as if multiple events were found at once.
    
    Expects the following environment variables to be set:
    QUEUE_TARGET_ESPRESSIF, QUEUE_TARGET_INFINEON, QUEUE_TARGET_MICROCHIP, QUEUE_TARGET_GENERATED
    
    Supports both new multi-value and legacy single-value parameters:
    New: POLICY_NAMES, THING_GROUP_NAMES (comma-delimited)
    Legacy: POLICY_NAME, THING_GROUP_NAME (single values)
    Thing Type: THING_TYPE_NAME (always singular - AWS IoT limitation)
    """
    config = {}
    
    # Try new multi-value parameters first, fall back to legacy
    e_policies = os.environ.get('POLICY_NAMES', '')
    e_thing_groups = os.environ.get('THING_GROUP_NAMES', '')
    
    # Backward compatibility: if new params empty, try legacy
    if not e_policies:
        e_policies = os.environ.get('POLICY_NAME', '')
    if not e_thing_groups:
        e_thing_groups = os.environ.get('THING_GROUP_NAME', '')
    
    # Thing type is always singular (AWS IoT limitation: one thing type per thing)
    e_thing_type = os.environ.get('THING_TYPE_NAME', '')

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
    config['bucket'] = bucket_name

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
                thing_group_arn = get_thing_group_arn(thing_group_name, default_session)
                thing_groups.append({'name': thing_group_name, 'arn': thing_group_arn})
        if thing_groups:
            config['thing_groups'] = thing_groups

    # Parse and validate thing type (singular - AWS IoT allows only one thing type per thing)
    if e_thing_type and check_cfn_prop_valid(e_thing_type):
        get_thing_type_arn(e_thing_type, default_session)
        config['thing_type_name'] = e_thing_type

    try:
        queue_url = get_provider_queue(config['bucket'])
    except ValueError as e:
        logger.error("Queue URL could not be resolved for bucket %s. Exiting.", config['bucket'])
        raise e

    for record in records_list:
        config['key'] = record.s3.get_object.key

        if config['bucket'].startswith(GENERATED_BUCKET_PREFIX):
            logger.info("Processing generated certificate file: %s", record.s3.get_object.key)
        else:
            logger.info("Processing vendor certificate manifest: %s", record.s3.get_object.key)

        send_sqs_message(config, queue_url, default_session)
        logger.info("Sent message to queue %s for s3://%s/%s",
                    queue_url, bucket_name, record.s3.get_object.key)

    return raw_event

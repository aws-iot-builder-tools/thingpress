"""
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

Lambda function provides data enrichment before passing along to the importer.
"""
import os
import logging

from boto3 import Session
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.utilities.data_classes import S3Event
from aws_utils import get_policy_arn, get_thing_group_arn, get_thing_type_arn, send_sqs_message
from aws_utils import check_cfn_prop_valid

logger = logging.getLogger()
logger.setLevel("INFO")

default_session: Session = Session()

ESPRESSIF_BUCKET_PREFIX = "thingpress-espressif-"
INFINEON_BUCKET_PREFIX = "thingpress-infineon-"
MICROCHIP_BUCKET_PREFIX = "thingpress-microchip-"
GENERATED_BUCKET_PREFIX = "thingpress-generated-"

def get_provider_queue(bucket_name: str) -> str:
    """
    Returns the queue related to the prefix of a given bucket
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

def lambda_handler(event: S3Event,
                   context: LambdaContext) -> dict: # pylint: disable=unused-argument
    """
    Lambda function main entry point. Verifies the S3 object can be read and resolves
    inputs prior to forwarding to vendor handler queue.

    This lambda function expects invocation by S3 event. There should be only one
    event, but is processed as if multiple events were found at once.
    
    Expects the following environment variables to be set:
    QUEUE_TARGET_ESPRESSIF
    QUEUE_TARGET_INFINEON
    QUEUE_TARGET_MICROCHIP
    QUEUE_TARGET_GENERATED
    
    Expects at least one of the following environment variables to be set:
    POLICY_NAME
    THING_GROUP_NAME

    May have the following environment variables set:
    THING_TYPE_NAME
    """
    # Get the payload coming in and process it.  There might be more than one.
    config = {}
    queue_url = None

    e_thing_group = os.environ['THING_GROUP_NAME']
    e_thing_type = os.environ['THING_TYPE_NAME']
    e_policy = os.environ['POLICY_NAME']

    config['bucket'] = event.bucket_name

    if check_cfn_prop_valid(e_thing_group):
        config['thing_group_arn'] = get_thing_group_arn(e_thing_group, default_session)

    if check_cfn_prop_valid(e_thing_type):
        get_thing_type_arn(e_thing_type, default_session)
        config['thing_type_name'] = e_thing_type

    if check_cfn_prop_valid(e_policy):
        get_policy_arn(e_policy, default_session)
        config['policy_name'] = e_policy

    try:
        queue_url = get_provider_queue(config['bucket'])
    except ValueError as e:
        logger.error(f"Queue URL could not be resolved for bucket {config['bucket']}. Exiting.")
        raise e

    for record in event.records:
        # TODO: verify s3 object, for now assume it is reachable
        # v_object = verify_s3_object(bucket, record.s3.get_object.key)
        config['key'] = record.s3.get_object.key
        
        # Log the provider type based on the bucket name
        if config['bucket'].startswith(GENERATED_BUCKET_PREFIX):
            logger.info(f"Processing generated certificate file: {record.s3.get_object.key}")
        else:
            logger.info(f"Processing vendor certificate manifest: {record.s3.get_object.key}")
            
        send_sqs_message(config, queue_url, default_session)

    return event.raw_event

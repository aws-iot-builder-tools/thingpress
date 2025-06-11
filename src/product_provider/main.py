"""
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

Lambda function provides data enrichment before passing along to the importer.
"""
import os
import json
import boto3

from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.utilities.data_classes import S3Event
from aws_utils import get_policy_arn, get_thing_group_arn, get_thing_type_arn

espressif_bucket_prefix = "thingpress-espressif-"
infineon_bucket_prefix = "thingpress-infineon-"
microchip_bucket_prefix = "thingpress-microchip-"

def process(payload: hash, queue_url: str) -> hash:
    """Annotate payload with environment-passed variants, later this function
       will evolve to allow importing types, groups, and policies"""

    # Pass on to the queue for target processing.
    client = boto3.client("sqs")
    client.send_message( QueueUrl=queue_url,
                         MessageBody=json.dumps(payload))
    return payload

def get_provider_queue(bucket_name: str) -> str:
    """
    Returns the queue related to the prefix of a given bucket
    The cfn stack prescribes the environment variable value.
    See the cfn template for more detail.
    """
    if bucket_name.startswith(espressif_bucket_prefix):
        return os.environ.get('QUEUE_TARGET_ESPRESSIF')
    if bucket_name.startswith(infineon_bucket_prefix):
        return os.environ.get('QUEUE_TARGET_INFINEON')
    if bucket_name.startswith(microchip_bucket_prefix):
        return os.environ.get('QUEUE_TARGET_MICROCHIP')
    return None

def lambda_handler(event: S3Event, context: LambdaContext) -> dict: # pylint: disable=unused-argument
    """
    Lambda function main entry point. Verifies the S3 object can be read and resolves
    inputs prior to forwarding to vendor handler queue.

    This lambda function expects invocation by S3 event. There should be only one
    event, but is processed as if multiple events were found at once.
    
    Expects the following environment variables to be set:
    QUEUE_TARGET_ESPRESSIF
    QUEUE_TARGET_INFINEON
    QUEUE_TARGET_MICROCHIP
    
    Expects at least one of the following environment variables to be set:
    POLICY_NAME
    THING_GROUP_NAME

    May have the following environment variables set:
    THING_TYPE_NAME
    """
    # Get the payload coming in and process it.  There might be more than one.
    v_thing_group = get_thing_group_arn(os.environ.get('THING_GROUP_NAME'))
    v_thing_type = get_thing_type_arn(os.environ.get('THING_TYPE_NAME'))
    v_policy = get_policy_arn(os.environ.get('POLICY_NAME'))

    s3_event = S3Event(event)
    queue_url = get_provider_queue(s3_event.bucket_name)
    data = {
        'policy_arn': v_policy,
        'thing_group_arn': v_thing_group,
        'thing_type_arn': v_thing_type,
        'bucket': s3_event.bucket_name
    }

    for record in s3_event.records:
        # TODO: verify s3 object, for now assume it is reachable
        # v_object = verify_s3_object(bucket, record.s3.get_object.key)
        data['key'] = record.s3.get_object.key
        process(data, queue_url)
    return event

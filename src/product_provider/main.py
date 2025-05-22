"""
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

Lambda function provides data enrichment before passing along to the importer.
"""
import os
import json
import boto3
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.utilities.data_classes import SQSEvent

def process(payload):
    """Annotate payload with environment-passed variants, later this function
       will evolve to allow importing types, groups, and policies"""

    queue_url = os.environ.get('QUEUE_TARGET')

    # Policy is required.
    payload['policy_name'] = os.environ.get('POLICY_NAME')

    # Thing group is desired, but optional.
    # The reason why 'None' has to be set is an environment variable
    # on a Lambda function cannot be set to empty
    if os.environ.get('THING_GROUP_NAME') == "None":
        payload['thing_group_name'] = None
    else:
        payload['thing_group_name'] = os.environ.get('THING_GROUP_NAME')

    # Thing group is desired, but optional.
    if os.environ.get('THING_TYPE_NAME') == "None":
        payload['thing_type_name'] = None
    else:
        payload['thing_type_name'] = os.environ.get('THING_TYPE_NAME')

    # Pass on to the queue for target processing.
    client = boto3.client("sqs")
    client.send_message( QueueUrl=queue_url,
                         MessageBody=json.dumps(payload))
    return payload

def lambda_handler(event: SQSEvent, context: LambdaContext) -> dict: # pylint: disable=unused-argument
    """Lambda function main entry point"""
    # Get the payload coming in and process it.  There might be more than one.
    result = []
    for record in event['Records']:
        r = process(json.loads(record["body"]))
        result.append(r)
    return result

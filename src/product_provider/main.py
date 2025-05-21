"""
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

Lambda function provides data enrichment before passing along to the importer.
"""
import os
import json
import boto3

def process(payload):

    # queue url is 
    queueUrl = os.environ.get('QUEUE_TARGET')

    # Policy is required.
    payload['policy_name'] = os.environ.get('POLICY_NAME')

    # Thing group is desired, but optional.
    # The reason why 'None' has to be set is an environment variable 
    # on a Lambda function cannot be set to empty
    
    if (os.environ.get('THING_GROUP_NAME') == "None"):
        payload['thing_group_name'] = ""
    else:
        payload['thing_group_name'] = os.environ.get('THING_GROUP_NAME')

    # Thing group is desired, but optional.
    if (os.environ.get('THING_TYPE_NAME') == "None"):
        payload['thing_type_name'] = ""
    else:
        payload['thing_type_name'] = os.environ.get('THING_TYPE_NAME')

    # Pass on to the queue for target processing.
    print(json.dumps(payload))

    client = boto3.client("sqs")
    client.send_message( QueueUrl=queueUrl,
                         MessageBody=json.dumps(payload))

def lambda_handler(event, context):

    # Get the payload coming in and process it.  There might be more than one.
    for record in event['Records']:
        process(json.loads(record["body"]))

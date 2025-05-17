# Copyright (C) 2020 Amazon.com, Inc. All Rights Reserved.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of
# this software and associated documentation files (the "Software"), to deal in
# the Software without restriction, including without limitation the rights to
# use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
# the Software, and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
# FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
# COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
# IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

# This lambda focuses on data enrichment before passing along to the importer.

import json
import boto3
import os

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

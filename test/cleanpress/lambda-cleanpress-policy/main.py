import boto3
import botocore
import json
import os

def process(payload):
    sqs_client = boto3.client("sqs")
    iot_client = boto3.client("iot")
    
    queueUrl = os.environ.get('QUEUE_TARGET')

    try:
        response = iot_client.list_attached_policies( target=payload['certificateArn'] )
    except botocore.exceptions.ClientError as error:
        if error.response['Error']['Code'] == 'ResourceNotFoundException':
            print("ERROR: The certificate has disappeared? Don't pass on the message.")
        if error.response['Error']['Code'] == 'UnauthorizedException':
            print("ERROR: Unable to make API call.")
        return None
    except:
        print("ERROR: Unexpected fault")
        return None

    if 'policies' in response:
        for policy in response['policies']:
            iot_client.detach_policy( policyName=policy['policyName'],
                                      target=payload['certificateArn'] )

    sqs_client.send_message( QueueUrl=queueUrl,
                             MessageBody=json.dumps(payload))

def lambda_handler(event, context):

    for record in event['Records']:
        process(json.loads(record["body"]))

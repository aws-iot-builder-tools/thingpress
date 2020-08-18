import boto3
import json
import os

def process(payload):
    sqs_client = boto3.client("sqs")
    iot_client = boto3.client("iot")
    
    queueUrl = os.environ.get('QUEUE_TARGET')

    response = iot_client.list_principal_things( principal=payload['certificateArn'] )

    for thing in response['things']:
        iot_client.detach_thing_principal( thingName=thing,
                                           principal=payload['certificateArn'] )
        iot_client.delete_thing( thingName=thing )

    sqs_client.send_message( QueueUrl=queueUrl,
                             MessageBody=json.dumps(payload))

def lambda_handler(event, context):

    for record in event['Records']:
        process(json.loads(record["body"]))

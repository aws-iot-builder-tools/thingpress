import boto3
import json
import os

def process(certificates):
    sqs_client = boto3.client("sqs")
    queueUrl = os.environ.get('QUEUE_STAGING')

    for record in certificates:
        payload = {}
        payload['certificateId'] = record['certificateId']
        payload['certificateArn'] = record['certificateArn']
        sqs_client.send_message( QueueUrl=queueUrl,
                                 MessageBody=json.dumps(payload))

def reformat_payload(payload):
    result = []
    id=-0
    for record in payload:
        new = {}
        new['Id'] = str("id" + str(id))
        new['MessageBody'] = record['Body']
        result.append(new)
        id = id + 1
    return result
    
def move_targets():
    sqs_client = boto3.client("sqs")
    queueStaging = os.environ.get('QUEUE_STAGING')
    queueTarget = os.environ.get('QUEUE_TARGET')

    while True:
        r_response = sqs_client.receive_message( QueueUrl=queueStaging,
                                                 MaxNumberOfMessages=10 )
        if not 'Messages' in r_response:
            break

        new_payload = reformat_payload(r_response['Messages'])
        s_response = sqs_client.send_message_batch( QueueUrl=queueTarget,
                                                    Entries=new_payload)

        for record in r_response['Messages']:
            sqs_client.delete_message(QueueUrl=queueStaging,
                                      ReceiptHandle=record['ReceiptHandle'])

def lambda_handler(event, context):
    sqs_client = boto3.client("sqs")
    iot_client = boto3.client("iot")

    response = iot_client.list_certificates( pageSize=250 )

    # Stage individual certificate deletion targets in 'cache' since
    # we need to paginate and tainting the set in mid flight causes
    # page marker resets
    iter=0
    
    while True:
        iter=iter+1
        print(iter)
        process(response['certificates'])
        response = iot_client.list_certificates( pageSize=250, marker=response['nextMarker'] )
        if not 'nextMarker' in response:
            process(response['certificates'])
            break

    # Move certificate deletion targets from staging cache to start of
    # deletion pipeline, causing events to carry them to completion

    move_targets()

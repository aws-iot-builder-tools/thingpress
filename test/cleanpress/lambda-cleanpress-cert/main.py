import boto3
import json

def process(payload):
    iot_client = boto3.client("iot")

    response = iot_client.list_principal_things( principal=payload['certificateArn'] )

    iot_client.update_certificate(certificateId=payload['certificateId'], newStatus='INACTIVE')
    iot_client.delete_certificate(certificateId=payload['certificateId'])

def lambda_handler(event, context):

    for record in event['Records']:
        process(json.loads(record["body"]))

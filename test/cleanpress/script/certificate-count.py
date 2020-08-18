import boto3
import json
import os

total = 0
def process(certificates):
    global total
    iot_client = boto3.client("iot")

    for record in certificates:
        total = total + 1

def lambda_handler(event, context):
    global total
    iot_client = boto3.client("iot")

    response = iot_client.list_certificates( pageSize=250 )

    while True:
        process(response['certificates'])
        if not 'nextMarker' in response:
            break
        response = iot_client.list_certificates( pageSize=250, marker=response['nextMarker'] )
    print(total)

lambda_handler(None, None)

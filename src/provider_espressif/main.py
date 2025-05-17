import os
import io
import json
import csv
import botocore
from boto3 import resource, client, s3
import botocore
from moto import mock_aws, settings
from aws_lambda_powertools.utilities.validation import validate
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
import base64

from schemas import INPUT_SCHEMA, OUTPUT_SCHEMA
from testable import LambdaSQSClass, LambdaS3Class

# Given a bucket and object, verify its existence and return the resource.
def s3_object_stream(bucket_name: str, object_name: str):
    s3 = resource('s3')
    res = s3.Object(bucket_name=bucket_name, key=object_name)
    try: 
        fs = io.BytesIO()
        res.download_fileobj(fs)
        return fs
    except botocore.exceptions.ClientError as ce:
        raise ce

# Given a bucket name and object name, return bytes representing
# the object content.
def s3_filebuf_bytes(bucket_name: str, object_name: str):
    object_stream = s3_object_stream(bucket_name=bucket_name,
                                     object_name=object_name)
    return object_stream.getvalue()

def format_certificate(certString):
    encodedCert = certString.encode('ascii')

    pem_obj = x509.load_pem_x509_certificate(encodedCert,
                                             backend=default_backend())
    block = pem_obj.public_bytes(encoding=serialization.Encoding.PEM).decode('ascii')
    return {'certificate': str(base64.b64encode(block.encode('ascii')))}

def invoke_export(bucket_name: str, object_name: str, queueUrl: str):
    sqs_client = client("sqs")
    manifest_bytes = s3_filebuf_bytes(bucket_name, object_name)
    reader_list = csv.DictReader(io.StringIO(manifest_bytes.decode()))

    for row in reader_list:
        thing_name = row['MAC']
        cert = row['cert']
        certificate_data = format_certificate(cert)
        certificate_data['thing'] = thing_name
        sqs_client.send_message( QueueUrl=queueUrl,
                             MessageBody=json.dumps(certificate_data) )

def lambda_handler(event, context):
    queueUrl = os.environ['QUEUE_TARGET']
    bucket_name = event['Records'][0]['s3']['bucket']['name']
    manifest_name = event['Records'][0]['s3']['object']['key'] 

    invoke_export(bucket_name, manifest_name, queueUrl)

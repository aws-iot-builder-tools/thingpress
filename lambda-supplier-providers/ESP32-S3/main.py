import os
import io
import boto3
import json
import csv
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
import base64

def s3_filebuf_bytes(bucket, obj):
    s3 = boto3.resource('s3')
    bucket = s3.Bucket(bucket)
    obj = bucket.Object(obj)
    file_stream = io.BytesIO()
    obj.download_fileobj(file_stream)
    return file_stream.getvalue()

def format_certificate(certString):
    encodedCert = certString.encode('ascii')

    pem_obj = x509.load_pem_x509_certificate(encodedCert,
                                         backend=default_backend())
    block = pem_obj.public_bytes(encoding=serialization.Encoding.PEM).decode('ascii')
    return {'certificate': str(base64.b64encode(block.encode('ascii')))}

def invoke_export(manifest, queueUrl):
    client = boto3.client("sqs")
    reader_list = csv.DictReader(io.StringIO(manifest.decode()))
    for row in reader_list:
        thing_name = row['esp_mac']
        cert = row['certs']
        certificate_data = format_certificate(cert)
        certificate_data['thing'] = thing_name
        client.send_message( QueueUrl=queueUrl,
                             MessageBody=json.dumps(certificate_data) )
        
def lambda_handler(event, context):
    queueUrl = os.environ['QUEUE_TARGET']

    bucket = event['Records'][0]['s3']['bucket']['name']
    manifest = event['Records'][0]['s3']['object']['key'] 

    manifestContent = s3_filebuf_bytes(bucket, manifest)

    invoke_export(manifestContent, queueUrl)

import os
import io
import json
import csv
from base64 import b64encode
import botocore
from boto3 import resource, client, s3
from moto import mock_aws, settings
from aws_lambda_powertools.utilities.validation import validate
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization

# Given a bucket and object, verify its existence and return the resource.
def s3_object_stream(bucket_name: str, object_name: str):
    """Retrieve an s3 object and read as stream"""
    s3res = resource('s3')
    res = s3res.Object(bucket_name=bucket_name, key=object_name)
    try:
        fs = io.BytesIO()
        res.download_fileobj(fs)
        return fs
    except botocore.exceptions.ClientError as ce:
        raise ce

# Given a bucket name and object name, return bytes representing
# the object content.
def s3_filebuf_bytes(bucket_name: str, object_name: str):
    """Flush s3 object stream buffer to string object"""
    object_stream = s3_object_stream(bucket_name=bucket_name,
                                     object_name=object_name)
    return object_stream.getvalue()

def format_certificate(cert_string):
    """Encode certificate so that it can safely travel via sqs"""
    cert_encoded = cert_string.encode('ascii')

    pem_obj = x509.load_pem_x509_certificate(cert_encoded,
                                             backend=default_backend())
    block = pem_obj.public_bytes(encoding=serialization.Encoding.PEM).decode('ascii')
    return str(b64encode(block.encode('ascii')))

def queue_certificate(identity, certificate, queue_url):
    """Send the thing name and certificate to sqs queue"""
    sqs_client = client("sqs")
    payload = {
        'thing': identity,
        'certificate': certificate
    }
    sqs_client.send_message( QueueUrl=queue_url,
                             MessageBody=json.dumps(payload) )

def invoke_export(bucket_name: str, object_name: str, queue_url: str):
    """Function to Iterate through the certificate list and queue for processing"""
    manifest_bytes = s3_filebuf_bytes(bucket_name, object_name)
    reader_list = csv.DictReader(io.StringIO(manifest_bytes.decode()))

    for row in reader_list:
        queue_certificate(row['MAC'], row['cert'], queue_url)

def lambda_handler(event, context):
    """Lambda function main entry point"""
    queue_url = os.environ['QUEUE_TARGET']
    bucket_name = event['Records'][0]['s3']['bucket']['name']
    manifest_name = event['Records'][0]['s3']['object']['key'] 

    invoke_export(bucket_name, manifest_name, queue_url)

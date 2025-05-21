"""
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

Lambda function to decompose Espressif based certificate manifest(s) and begin
the import processing pipeline
"""
import os
import io
import json
import csv
from base64 import b64encode
import botocore
from boto3 import resource, client
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.utilities.data_classes import S3Event

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

def lambda_handler(event: dict, context: LambdaContext) -> dict:
    """Lambda function main entry point"""
    s3_event = S3Event(event)
    queue_url = os.environ['QUEUE_TARGET']

    bucket = s3_event.bucket_name
    for record in s3_event.records:
        manifest = record.s3.get_object.key
        invoke_export(bucket, manifest, queue_url)
    return event

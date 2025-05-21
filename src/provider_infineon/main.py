"""
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

Lambda function to decompose Infineon based certificate manifest(s) and begin
the import processing pipeline
"""
import os
import io
import json
from xml.etree import ElementTree
from base64 import b64encode
from botocore import exceptions as botoexceptions
from boto3 import resource as boto3resource, client as boto3client
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.utilities.data_classes import S3Event, event_source

def s3_object_stream(bucket_name: str, object_name: str):
    """Given a bucket and object, verify its existence and return the resource."""
    s3 = boto3resource('s3')
    res = s3.Object(bucket_name=bucket_name, key=object_name)
    try:
        fs = io.BytesIO()
        res.download_fileobj(fs)
        return fs
    except botoexceptions.ClientError as ce:
        raise ce


def s3_filebuf_bytes(bucket_name: str, object_name: str):
    """ Given a bucket name and object name, return bytes representing
        the object content."""
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
    sqs_client = boto3client("sqs")
    payload = {
        'thing': identity,
        'certificate': certificate
    }
    sqs_client.send_message( QueueUrl=queue_url,
                             MessageBody=json.dumps(payload) )

def invoke_export(manifest, queue_url):
    """Function to Iterate through the certificate list and queue for processing"""
    root = ElementTree.fromstring(manifest)

    for group in root.findall('group'): # /binaryhex
        thing_name = ''

        # TODO: Evaluate what happens when this fails
        for hex_element in group.findall('hex'):
            if hex_element.get('name') == 'TpmMAC':
                thing_name = hex_element.get('value')

        for hexdata_element in group.findall('binaryhex'):
            certificate_data = format_certificate(hexdata_element.text)
            queue_certificate(thing_name, certificate_data, queue_url)

def lambda_handler(event: dict, context: LambdaContext) -> dict:
    """Lambda function main entry point"""
    s3_event = S3Event(event)
    queue_url = os.environ['QUEUE_TARGET']

    bucket = s3_event.bucket_name
    for record in s3_event.records:
        manifest = record.s3.get_object.key
        manifest_content = s3_filebuf_bytes(bucket, manifest)
        invoke_export(manifest_content, queue_url)
    return event

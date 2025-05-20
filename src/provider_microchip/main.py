"""
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

Lambda function to import Microchip manifest
"""
import os
import io
#from base64 import b64encode
#from lsplib import s3_filebuf_bytes
import boto3
from .manifest_handler import invoke_export

def s3_filebuf_bytes(bucket, obj):
    s3 = boto3.resource('s3')
    bucket = s3.Bucket(bucket)
    obj = bucket.Object(obj)
    file_stream = io.BytesIO()
    obj.download_fileobj(file_stream)
    return file_stream.getvalue()

def lambda_handler(event, context):
    queue_url = os.environ['QUEUE_TARGET']
    verify_certname = os.environ['VERIFY_CERT']
    
    # there can be only one manifest file per event?  Need to verify
    # this

    bucket_name = event['Records'][0]['s3']['bucket']['name']
    manifest_filename = event['Records'][0]['s3']['object']['key'] 

    # Get the manifest file and the integrity verification certificate from S3.

    manifest_content = s3_filebuf_bytes(bucket_name, manifest_filename)
    verifycert_content = s3_filebuf_bytes(bucket_name, verify_certname)

    invoke_export(manifest_content, verifycert_content, queue_url)

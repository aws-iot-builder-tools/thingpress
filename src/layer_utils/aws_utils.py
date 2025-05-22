"""
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

AWS related functions that multiple lambda functions use, here to reduce redundancy
"""
from io import BytesIO
from json import dumps
from botocore.exceptions import ClientError
from boto3 import resource, client

# Given a bucket and object, verify its existence and return the resource.
def s3_object_stream(bucket_name: str, object_name: str):
    """Retrieve an s3 object and read as stream"""
    s3res = resource('s3')
    res = s3res.Object(bucket_name=bucket_name, key=object_name)
    try:
        fs = BytesIO()
        res.download_fileobj(fs)
        return fs
    except ClientError as ce:
        raise ce

# Given a bucket name and object name, return bytes representing
# the object content.
def s3_filebuf_bytes(bucket_name: str, object_name: str):
    """Flush s3 object stream buffer to string object"""
    object_stream = s3_object_stream(bucket_name=bucket_name,
                                     object_name=object_name)
    return object_stream.getvalue()

def queue_manifest_certificate(identity, certificate, queue_url):
    """Send the thing name and certificate to sqs queue"""
    sqs_client = client("sqs")
    payload = {
        'thing': identity,
        'certificate': certificate
    }
    sqs_client.send_message( QueueUrl=queue_url,
                             MessageBody=dumps(payload) )

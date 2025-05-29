"""
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

AWS related functions that multiple lambda functions use, here to reduce redundancy
"""
import logging
from io import BytesIO, StringIO
from json import dumps
from botocore.exceptions import ClientError
from boto3 import resource, client

logger = logging.getLogger()
logger.setLevel("INFO")

def s3_object(bucket_name: str, object_name: str, fs=BytesIO()):
    """Retrieve an s3 object and return as file-like object.
       By default, it returns a byte-like object."""
    s3res = resource('s3')
    res = s3res.Object(bucket_name=bucket_name, key=object_name)
    try:
        res.download_fileobj(fs)
        return fs
    except ClientError as ce:
        raise ce

def s3_object_bytes(bucket_name: str, object_name: str, getvalue: bool=False):
    """Download an S3 object as byte file-like object"""
    fs = BytesIO()
    s3_object(bucket_name, object_name, fs)
    if getvalue is True:
        return fs.getvalue()
    return BytesIO(fs.getvalue())

def s3_object_str(bucket_name: str, object_name: str, getvalue: bool=False):
    """Download an S3 object as string file-like object"""
    fs = StringIO()
    s3_object(bucket_name, object_name, fs)
    if getvalue is True:
        return fs.getvalue()
    return fs

# TODO: Deprecate, use s3_object_bytes or s3_object_str instead
def s3_filebuf_bytes(bucket_name: str, object_name: str):
    """Flush s3 object stream buffer to string object
       Given a bucket name and object name, return bytes representing
       the object content."""
    object_stream = s3_object(bucket_name=bucket_name,
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

def verify_queue(queue_url: str) -> bool:
    """Verify the queue exists by attempting to fetch its attributes"""
    s = client("sqs")
    try:
        s.get_queue_attributes(QueueUrl=queue_url,
                               AttributeNames=['CreatedTimestamp'])
    except ClientError as error:
        error_code = error.response['Error']['Code']
        if error_code == 'QueueDoesNotExist':
            logger.error("Queue {queue_url} does not exist")
        else:
            logger.error("Unexpected exception {error_code}")
        return False
    return True

# Copyright (C) 2020 Amazon.com, Inc. All Rights Reserved.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of
# this software and associated documentation files (the "Software"), to deal in
# the Software without restriction, including without limitation the rights to
# use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
# the Software, and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
# FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
# COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
# IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

import jmespath
import json
import uuid
import boto3
import os
import io
from base64 import b64encode
from ManifestHandler import invoke_export

def s3_filebuf_bytes(bucket, obj):
    s3 = boto3.resource('s3')
    bucket = s3.Bucket(bucket)
    obj = bucket.Object(obj)
    file_stream = io.BytesIO()
    obj.download_fileobj(file_stream)
    return file_stream.getvalue()

def lambda_handler(event, context):
    queueUrl = os.environ['QUEUE_TARGET']
    verifyCertname = os.environ['VERIFY_CERT']
    
    # there can be only one manifest file per event?  Need to verify
    # this

    bucketName = event['Records'][0]['s3']['bucket']['name']
    manifestFilename = event['Records'][0]['s3']['object']['key'] 

    # Get the manifest file and the integrity verification certificate from S3.

    manifestContent = s3_filebuf_bytes(bucketName, manifestFilename)
    verifycertContent = s3_filebuf_bytes(bucketName, verifyCertname)

    invoke_export(manifestContent, verifycertContent, queueUrl)

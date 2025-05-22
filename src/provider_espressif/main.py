"""
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

Lambda function to decompose Espressif based certificate manifest(s) and begin
the import processing pipeline
"""
import os
import io
import csv
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.utilities.data_classes import S3Event
from aws_utils import s3_filebuf_bytes, queue_manifest_certificate

def invoke_export(bucket_name: str, object_name: str, queue_url: str):
    """Evaluate CSV based Espressif manifest"""
    manifest_bytes = s3_filebuf_bytes(bucket_name, object_name)
    reader_list = csv.DictReader(io.StringIO(manifest_bytes.decode()))

    for row in reader_list:
        queue_manifest_certificate(row['MAC'], row['cert'], queue_url)

def lambda_handler(event: dict, context: LambdaContext) -> dict: # pylint: disable=unused-argument
    """Lambda function main entry point"""
    s3_event = S3Event(event)
    queue_url = os.environ['QUEUE_TARGET']

    bucket = s3_event.bucket_name
    for record in s3_event.records:
        manifest = record.s3.get_object.key
        invoke_export(bucket, manifest, queue_url)
    return event

"""
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

Lambda function to import Microchip manifest
"""
import os
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.utilities.data_classes import S3Event
from aws_utils import s3_filebuf_bytes
from .manifest_handler import invoke_export

def lambda_handler(event: S3Event, context: LambdaContext) -> dict: # pylint: disable=unused-argument
    """Lambda function main entry point"""
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

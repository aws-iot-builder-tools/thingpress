"""
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

Lambda function to decompose Infineon based certificate manifest(s) and begin
the import processing pipeline
"""
import os
from xml.etree import ElementTree
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.utilities.data_classes import S3Event
from aws_utils import s3_filebuf_bytes, queue_manifest_certificate
from cert_utils import format_certificate

def invoke_export(manifest, queue_url):
    """This is old process, to be revised"""
    root = ElementTree.fromstring(manifest)

    for group in root.findall('group'): # /binaryhex
        thing_name = ''

        # TODO: Evaluate what happens when this fails
        for hex_element in group.findall('hex'):
            if hex_element.get('name') == 'TpmMAC':
                thing_name = hex_element.get('value')

        for hexdata_element in group.findall('binaryhex'):
            certificate_data = format_certificate(hexdata_element.text)
            queue_manifest_certificate(thing_name, certificate_data, queue_url)

def lambda_handler(event: dict, context: LambdaContext) -> dict: # pylint: disable=unused-argument
    """Lambda function main entry point"""
    s3_event = S3Event(event)
    queue_url = os.environ['QUEUE_TARGET']

    bucket = s3_event.bucket_name
    for record in s3_event.records:
        manifest = record.s3.get_object.key
        manifest_content = s3_filebuf_bytes(bucket, manifest)
        invoke_export(manifest_content, queue_url)
    return event

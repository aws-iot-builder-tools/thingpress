"""
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

Lambda function to import Microchip manifest
"""
import os
import json
from boto3 import Session
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.utilities.data_classes import SQSEvent
import sys
import os

# Handle imports for both Lambda and unit test environments
try:
    # Try Lambda environment first - flattened structure
    from provider_microchip.manifest_handler import invoke_export
except ImportError:
    try:
        # Try unit test environment - nested structure  
        from .manifest_handler import invoke_export
    except ImportError:
        # Last resort - add current directory to path and try again
        current_dir = os.path.dirname(os.path.abspath(__file__))
        sys.path.insert(0, current_dir)
        from manifest_handler import invoke_export

default_session: Session = Session()

def lambda_handler(event: SQSEvent, context: LambdaContext) -> dict: # pylint: disable=unused-argument
    """
    Process Microchip certificate manifests from SQS messages and forward to target queue.
    
    This Lambda function processes SQS messages containing S3 bucket and object information
    for Microchip certificate manifests. For each manifest:
    1. Extracts and validates the signed certificate data using the verification certificate
    2. Processes each certificate in the manifest, verifying digital signatures
    3. Extracts the certificate chain for each device
    4. Forwards the certificate data to the target SQS queue for further processing
    
    Environment variables:
        QUEUE_TARGET: URL of the SQS queue to forward processed certificates to
        VERIFY_CERT: Name of the verification certificate file
        VERIFICATION_CERTS_BUCKET: S3 bucket containing verification certificates
    
    Args:
        event (SQSEvent): SQS event containing messages with S3 bucket/object information
        context (LambdaContext): Lambda execution context (unused)
        
    Returns:
        dict: The original raw event for AWS Lambda SQS batch processing
    """
    queue_url = os.environ['QUEUE_TARGET']

    for record in event.records:
        config = json.loads(record["body"])
        invoke_export(config, queue_url, default_session)

    return event.raw_event

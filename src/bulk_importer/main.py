"""
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

Lambda function to import certificate, construct IoT Thing, and associate
the Thing, Policy, Certificate, Thing Type, and Thing Group
"""
import hashlib
import os
import random
from json import loads

from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.data_classes import SQSEvent
from aws_lambda_powertools.utilities.idempotency import idempotent_function
from aws_lambda_powertools.utilities.idempotency.config import IdempotencyConfig
from aws_lambda_powertools.utilities.idempotency.persistence.dynamodb import \
    DynamoDBPersistenceLayer
from aws_lambda_powertools.utilities.typing import LambdaContext
from boto3 import Session
from botocore.exceptions import ClientError
from layer_utils.aws_utils import (get_certificate, process_policy, process_thing,
                                   process_thing_group, process_thing_type, register_certificate)
from layer_utils.cert_utils import decode_certificate, get_certificate_fingerprint, load_certificate

# Initialize Logger and Idempotency
logger = Logger(service="bulk_importer")
default_session: Session = Session()

if os.environ.get("POWERTOOLS_IDEMPOTENCY_TABLE") is None:
    raise ValueError("Environment variable POWERTOOLS_IDEMPOTENCY_TABLE not set.")
POWERTOOLS_IDEMPOTENCY_TABLE: str = os.environ["POWERTOOLS_IDEMPOTENCY_TABLE"]
if os.environ.get("POWERTOOLS_IDEMPOTENCY_EXPIRY_SECONDS") is None:
    POWERTOOLS_IDEMPOTENCY_EXPIRY_SECONDS: int = 3600
POWERTOOLS_IDEMPOTENCY_EXPIRY_SECONDS: int = int(
    os.environ.get("POWERTOOLS_IDEMPOTENCY_EXPIRY_SECONDS", 3600))


# Initialize persistence layer for idempotency
persistence_layer = DynamoDBPersistenceLayer(
    table_name=POWERTOOLS_IDEMPOTENCY_TABLE,
    key_attr="id",
    expiry_attr="expiration",
    status_attr="status",
    data_attr="data",
    validation_key_attr="validation"
)

# Configure idempotency with jitter for high-volume processing
idempotency_config = IdempotencyConfig(
    # Use jitter_key_generator for jitter instead of event_key_jitter
    expires_after_seconds=POWERTOOLS_IDEMPOTENCY_EXPIRY_SECONDS
)

def certificate_key_generator(event, context):
    """Generate a unique key based on certificate content and thing name"""
    if isinstance(event, dict) and "certificate" in event and "thing" in event:
        # Use certificate hash and thing name as the key
        cert_hash = hashlib.sha256(event["certificate"].encode()).hexdigest()
        # Add some randomness to prevent hot keys

        jitter = random.random() * 0.3  # 30% jitter
        jitter_str = f"{jitter:.5f}"
        return f"{event['thing']}:{cert_hash[:16]}:{jitter_str}"
    return None

@idempotent_function(
    persistence_store=persistence_layer,
    config=idempotency_config,
    event_key_generator=certificate_key_generator,
    data_keyword_argument="config"
)
#TODO with idempotency added, may no longer need call to get_certificate.
#     in fact doing get_certificate on no cache hit might be detrimental
#     in the extremely improbable case of finding a non import certificate
#     with the same fingerprint
def process_certificate(config, session: Session=default_session):
    """ Imports the certificate to IoT Core """
    payload = config['certificate']

    decoded_certificate = decode_certificate(payload)
    x509_certificate = load_certificate(decoded_certificate)
    fingerprint = get_certificate_fingerprint(x509_certificate)

    try:
        response = get_certificate(fingerprint, session)
        logger.info({
            "message": "Certificate already found. Returning certificateId in"
                       "case this is recovering from a broken load",
            "fingerprint": fingerprint
        })
        return response
    except ClientError as error:
        logger.info({
            "message": "Certificate not found in IoT Core. Importing.",
            "fingerprint": fingerprint,
            "error": str(error)
        })
        return register_certificate(decoded_certificate.decode('ascii'),
                                    get_thingpress_tags(), session)

def get_thingpress_tags() -> list:
    """Generate standard Thingpress tags for IoT objects
    
    Returns:
        List of tags in AWS format: [{'Key': 'key', 'Value': 'value'}]
    """
    return [
        {'Key': 'created-by', 'Value': 'thingpress'},
        {'Key': 'managed-by', 'Value': 'thingpress'}
    ]

def process_sqs(config, session: Session=default_session):
    """Main processing function to procedurally run through processing steps."""
    certificate_id = process_certificate(config=config, session=session)

    logger.info({
        "message": "Processing thing and associations",
        "thing_name": config.get('thing'),
        "certificate_id": certificate_id
    })

    # Create standard Thingpress tags
    thingpress_tags = get_thingpress_tags()

    process_thing(config.get('thing'), certificate_id, tags=thingpress_tags, session=session)
    process_policy(config.get('policy_name'), certificate_id, session)
    process_thing_group(config.get('thing_group_arn'), config.get('thing'), session)
    process_thing_type(config.get('thing'), config.get('thing_type_name'), session)

    return {
        "certificate_id": certificate_id,
        "thing_name": config.get('thing')
    }

def lambda_handler(event: SQSEvent,
                   _context: LambdaContext) -> dict:
    """Lambda function main entry point"""

    for record in event['Records']:
        if record.get('eventSource') == 'aws:sqs':
            config = loads(record["body"])
            logger.info({
                "message": "Processing SQS message",
                "thing_name": config.get('thing')
            })
            process_sqs(config)

    return event.raw_event

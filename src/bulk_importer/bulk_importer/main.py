# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""Lambda function to import certificate, construct IoT Thing, and associate
the Thing, Policy, Certificate, Thing Type, and Thing Group
"""
import hashlib
import random
from json import loads

from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.idempotency import idempotent_function

from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.utilities.data_classes import SQSEvent
from boto3 import Session
from botocore.exceptions import ClientError
from layer_utils.aws_utils import (get_certificate, process_policy, process_thing,
                                   process_thing_group, process_thing_type, register_certificate)
from layer_utils.cert_utils import decode_certificate, get_certificate_fingerprint, load_certificate
from layer_utils.aws_utils import ImporterMessageKey, powertools_idempotency_environ

# Initialize Logger and Idempotency
logger = Logger(service="bulk_importer")
default_session: Session = Session()

persistence_layer, idempotency_config = powertools_idempotency_environ()

def certificate_key_generator(event: dict, _context):
    """Generate a unique key based on certificate content and thing name"""
    if not ImporterMessageKey.CERTIFICATE.value in event:
        return None

    if not ImporterMessageKey.THING_NAME.value in event:
        return None

    # Use certificate hash and thing name as the key
    cert_hash = hashlib.sha256(event[ImporterMessageKey.CERTIFICATE.value].encode()).hexdigest()

    # Add some randomness to prevent hot keys
    jitter = random.random() * 0.3  # 30% jitter
    jitter_str = f"{jitter:.5f}"
    return f"{event[ImporterMessageKey.THING_NAME.value]}:{cert_hash[:16]}:{jitter_str}"

@idempotent_function(
    persistence_store=persistence_layer,
    config=idempotency_config,
    event_key_generator=certificate_key_generator,
    data_keyword_argument="config"
)
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
        "thing_name": config.get(ImporterMessageKey.THING_NAME.value),
        "certificate_id": certificate_id
    })

    # Create standard Thingpress tags
    thingpress_tags = get_thingpress_tags()

    process_thing(config.get(ImporterMessageKey.THING_NAME.value),
                  certificate_id,
                  tags=thingpress_tags,
                  session=session)

    process_policy(config.get(ImporterMessageKey.POLICY_NAME.value),
                   certificate_id,
                   session=session)

    process_thing_group(config.get(ImporterMessageKey.THING_GROUP_ARN.value),
                        config.get(ImporterMessageKey.THING_NAME.value),
                        session=session)

    process_thing_type(config.get(ImporterMessageKey.THING_NAME.value),
                       config.get(ImporterMessageKey.THING_TYPE_NAME.value),
                       session=session)

    return {
        "certificate_id": certificate_id,
        "thing_name": config.get(ImporterMessageKey.THING_NAME.value)
    }

def lambda_handler(event: dict,
                   _context: LambdaContext) -> dict:
    """Lambda function main entry point"""
    sqs_event = SQSEvent(event)

    for record in sqs_event.records:
        config = loads(record.body)
        logger.info({
            "message": "Processing SQS message",
            "thing_name": config.get(ImporterMessageKey.THING_NAME.value)
        })
        process_sqs(config)

    return event

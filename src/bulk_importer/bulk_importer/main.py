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

from layer_utils.aws_utils import (
    get_certificate,
    get_thing_arn,
    process_policy,
    process_thing,
    process_thing_group,
    process_thing_type,
    register_certificate)
from layer_utils.cert_utils import (
    decode_certificate,
    get_certificate_fingerprint,
    load_certificate)
from layer_utils.aws_utils import (
    ImporterMessageKey,
    powertools_idempotency_environ,
    get_certificate_arn)

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
def process_certificate(config, session: Session=default_session) -> tuple[str,str]:
    """ Imports the certificate to IoT Core """
    payload = config['certificate']

    decoded_certificate = decode_certificate(payload)
    x509_certificate = load_certificate(decoded_certificate.encode('ascii'))
    fingerprint = get_certificate_fingerprint(x509_certificate)

    try:
        certificate_id = get_certificate(fingerprint, session)
    except ClientError as error:
        logger.info({
            "message": "Certificate not found in IoT Core. Importing.",
            "fingerprint": fingerprint,
            "error": str(error)
        })
        try:
            certificate_id = register_certificate(certificate=decoded_certificate,
                                        session=session)
        except ClientError as import_error:
            logger.error({
                "message": "Certificate could not be created.",
                "error": str(import_error)
            })
            raise

    certificate_arn = get_certificate_arn(certificate_id, session)
    return certificate_id, certificate_arn

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
    certificate_id, certificate_arn = process_certificate(config=config, session=session)

    logger.info({
        "message": "Processing thing and associations",
        "thing_name": config.get(ImporterMessageKey.THING_NAME.value),
        "certificate_id": certificate_id,
        "certificate_arn": certificate_arn
    })

    process_thing(config.get(ImporterMessageKey.THING_NAME.value),
                  certificate_arn=certificate_arn,
                  session=session)

    process_policy(policy_name=config.get(ImporterMessageKey.POLICY_NAME.value),
                   certificate_arn=certificate_arn,
                   session=session)

    thing_arn = get_thing_arn(config.get(ImporterMessageKey.THING_NAME.value, session),
                              session=session)
    process_thing_group(thing_group_arn=config.get(ImporterMessageKey.THING_GROUP_ARN.value),
                        thing_arn=thing_arn,
                        session=session)

    process_thing_type(thing_name=config.get(ImporterMessageKey.THING_NAME.value),
                       thing_type_name=config.get(ImporterMessageKey.THING_TYPE_NAME.value),
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

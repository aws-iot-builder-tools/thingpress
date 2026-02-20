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
    register_certificate,
    validate_and_get_certificate,
    activate_certificate,
    process_thing_attributes)
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
    """ Imports the certificate to IoT Core or looks up existing certificate by fingerprint """
    cert_format = config.get('cert_format', 'X509')

    # Phase 1 or Normal: X509 format - register new certificate
    if cert_format == 'X509':
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
                # Determine certificate status based on cert_active config
                # Default to 'TRUE' for backward compatibility (certificates active by default)
                # Note: AWS IoT RegisterCertificateWithoutCA only supports ACTIVE or INACTIVE
                # PENDING_ACTIVATION is not a valid status for registration
                cert_active = config.get('cert_active', 'TRUE')
                cert_status = 'ACTIVE' if cert_active == 'TRUE' else 'INACTIVE'

                certificate_id = register_certificate(
                    certificate=decoded_certificate,
                    status=cert_status,
                    session=session
                )
            except ClientError as import_error:
                logger.error({
                    "message": "Certificate could not be created.",
                    "error": str(import_error)
                })
                raise

        certificate_arn = get_certificate_arn(certificate_id, session)
        return certificate_id, certificate_arn

    # Phase 2: FINGERPRINT format - look up existing certificate
    if cert_format == 'FINGERPRINT':
        cert_fingerprint = config['certificate']
        logger.info({
            "message": "Looking up certificate by fingerprint",
            "fingerprint": cert_fingerprint
        })

        cert_info = validate_and_get_certificate(cert_fingerprint, session)
        certificate_id = cert_info['certificate_id']
        certificate_arn = cert_info['certificate_arn']

        # Activate certificate if it's not already ACTIVE and cert_active is TRUE
        # Default to 'TRUE' for backward compatibility
        # Handles both PENDING_ACTIVATION and INACTIVE statuses
        cert_active = config.get('cert_active', 'TRUE')
        if cert_info['status'] != 'ACTIVE' and cert_active == 'TRUE':
            logger.info({
                "message": "Activating certificate",
                "certificate_id": certificate_id,
                "current_status": cert_info['status']
            })
            activate_certificate(certificate_id, session)

        return certificate_id, certificate_arn

    raise ValueError(f"Invalid cert_format: {cert_format}. Must be 'X509' or 'FINGERPRINT'")

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

    # Default to 'FALSE' for backward compatibility
    thing_deferred = config.get('thing_deferred', 'FALSE')

    if thing_deferred == "FALSE":
        process_thing(config.get(ImporterMessageKey.THING_NAME.value),
                    certificate_arn=certificate_arn,
                    session=session)

        # Process thing type FIRST (before attributes)
        # AWS IoT allows only one thing type per thing
        # Thing Type is required to have more than 3 attributes
        thing_type_name = config.get(ImporterMessageKey.THING_TYPE_NAME.value)
        if thing_type_name:
            process_thing_type(thing_name=config.get(ImporterMessageKey.THING_NAME.value),
                            thing_type_name=thing_type_name,
                            session=session)

        # Process Thing attributes if provided (Phase 2: MES workflow)
        # Must be done AFTER Thing Type is assigned
        attributes = config.get('attributes')
        if attributes:
            logger.info({
                "message": "Processing Thing attributes",
                "thing_name": config.get(ImporterMessageKey.THING_NAME.value),
                "attribute_count": len(attributes)
            })
            process_thing_attributes(
                thing_name=config.get(ImporterMessageKey.THING_NAME.value),
                attributes=attributes,
                session=session
            )

    # Process multiple policies
    policies = config.get('policies', [])
    for policy_info in policies:
        process_policy(policy_name=policy_info['name'],
                      certificate_arn=certificate_arn,
                      session=session)

    if thing_deferred == "FALSE":
        thing_arn = get_thing_arn(config.get(ImporterMessageKey.THING_NAME.value),
                                session=session)

        # Process multiple thing groups
        thing_groups = config.get('thing_groups', [])
        for thing_group_info in thing_groups:
            process_thing_group(thing_group_arn=thing_group_info['arn'],
                            thing_arn=thing_arn,
                            session=session)

    result = {
        "certificate_id": certificate_id,
        "thing_name": config.get(ImporterMessageKey.THING_NAME.value)
    }

    if thing_deferred == "TRUE":
        result['thing_name'] = "DEFERRED"

    return result

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

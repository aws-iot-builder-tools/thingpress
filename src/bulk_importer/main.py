"""
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

Lambda function to import certificate, construct IoT Thing, and associate
the Thing, Policy, Certificate, Thing Type, and Thing Group
"""
from json import loads
import logging
from botocore.exceptions import ClientError
from boto3 import Session, _get_default_session
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.utilities.data_classes import SQSEvent
from cert_utils import decode_certificate, get_certificate_fingerprint, load_certificate
from aws_utils import get_certificate, register_certificate
from aws_utils import process_thing_group, process_policy, process_thing, process_thing_type
logger = logging.getLogger()
logger.setLevel("INFO")
default_session: Session = Session()

def process_certificate(config, session: Session=default_session):
    """ Imports the certificate to IoT Core """
    payload = config['certificate']

    decoded_certificate = decode_certificate(payload)
    x509_certificate = load_certificate(decoded_certificate)
    fingerprint = get_certificate_fingerprint(x509_certificate)

    try:
        response = get_certificate(fingerprint, session)
        logger.info("Certificate already found. Returning certificateId in case this "
                "is recovering from a broken load")
        return response
    except ClientError as error:
        logger.info("Certificate [%s] not found in IoT Core. Importing. %s", fingerprint, error)
        return register_certificate(decoded_certificate.decode('ascii'), session)

def process_sqs(config, session: Session=default_session):
    """Main processing function to procedurally run through processing steps."""
    certificate_id = process_certificate(config, session)
    process_thing(config.get('thing'), certificate_id, session)
    process_policy(config.get('policy_name'), certificate_id, session)
    process_thing_group(config.get('thing_group_arn'), config.get('thing'), session)
    process_thing_type(config.get('thing'), config.get('thing_type_name'), session)

def lambda_handler(event: SQSEvent,
                   context: LambdaContext) -> dict: # pylint: disable=unused-argument
    """Lambda function main entry point"""

    for record in event['Records']:
        if record.get('eventSource') == 'aws:sqs':
            config = loads(record["body"])
            process_sqs(config)

    return event.raw_event

"""
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

Lambda function to import certificate, construct IoT Thing, and associate
the Thing, Policy, Certificate, Thing Type, and Thing Group
"""
import ast
import base64
import json

import os
import logging
import botocore
from botocore.exceptions import ClientError
from boto3 import client as boto3client
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.backends import default_backend
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.utilities.data_classes import SQSEvent
from cert_utils import get_certificate_fingerprint

logger = logging.getLogger()
logger.setLevel("INFO")

def get_certificate(certificate_id):
    """Verify that the certificate is in IoT Core"""
    iot_client = boto3client('iot')
    try:
        response = iot_client.describe_certificate(certificateId=certificate_id)
        return response["certificateDescription"].get("certificateId")
    except ClientError as error:
        assert error.response['Error']['Code'] == 'ResourceNotFoundException'
        raise error

def get_certificate_arn(certificate_id):
    """Retrieve the certificate Arn."""
    iot_client = boto3client('iot')
    try:
        response = iot_client.describe_certificate(certificateId=certificate_id)
        return response["certificateDescription"].get("certificateArn")
    except ClientError as error:
        error_code = error.response['Error']['Code']
        error_message = error.response['Error']['Message']
        if error_code == 'ResourceNotFoundException':
            logger.error("get_certificate_arn failed: %s", error_message)
        # TODO: this should raise an exception
        raise error
#TODO: change this method to get_thing_arn
def get_thing(thing_name: str) -> str:
    """Retrieve the Thing ARN"""
    iot_client = boto3client('iot')
    try:
        response = iot_client.describe_thing(thingName=thing_name)
        return response.get("thingArn")
    except ClientError as error:
        error_code = error.response['Error']['Code']
        assert error_code == 'ResourceNotFoundException'
        return None

def process_policy(policy_name, certificate_id):
    """Attaches the IoT policy to the certificate"""
    if policy_name is None:
        return
    iot_client = boto3client('iot')
    iot_client.attach_policy(policyName=policy_name,
                             target=get_certificate_arn(certificate_id))

def process_thing(thing_name, certificate_id, thing_type_name=None):
    """Creates the IoT Thing if it does not already exist"""
    iot_client = boto3client('iot')
    certificate_arn = get_certificate_arn(certificate_id)
    try:
        iot_client.describe_thing(thingName=thing_name)
        return None
    except ClientError as error:
        error_code = error.response['Error']['Code'] # pylint: disable=unused-variable
        logger.info("Thing not found {error_code}. Creating.")

    # Create thing
    try:
        if thing_type_name is None:
            iot_client.create_thing(thingName=thing_name)
        else:
            iot_client.create_thing(thingName=thing_name,
                                    thingTypeName=thing_type_name)

    except ClientError as error:
        error_code = error.response['Error']['Code']
        logger.error("ERROR Thing creation failed: {error_code}")
        return None

    try:
        iot_client.attach_thing_principal(thingName=thing_name,
                                          principal=certificate_arn)
    except ClientError as error:
        print("ERROR Certificate attachment failed.")
        print(error)
    return None

def requeue(config):
    """
    Requeues the message for processing in case of unrecoverable error such
    as throttling. The structure is:
    { }
    """
    sqs_client = boto3client('sqs')
    sqs_client.send_message( QueueUrl=os.environ.get('QUEUE_TARGET'),
                             MessageBody=json.dumps(config))

def process_certificate(config, requeue_cb):
    """Imports the certificate to IoT Core
       TODO: This should be simplified"""
    iot_client = boto3client('iot')
    payload = config['certificate']
    certificate_text = base64.b64decode(ast.literal_eval(payload))

    # See if the certificate has already been registered.  If so, bail.
    certificate_obj = x509.load_pem_x509_certificate(data=certificate_text,
                                                     backend=default_backend())

    fingerprint = get_certificate_fingerprint(certificate_obj)

    try:
        get_certificate(fingerprint)
        response = iot_client.describe_certificate(certificateId=fingerprint)
        print("Certificate already found. Returning certificateId in case this "
                "is recovering from a broken load")
        return response["certificateDescription"].get("certificateId")
    except ClientError as error:
        logger.info("Certificate [%s] not found in IoT Core (%s). Importing.",
                    fingerprint, error.response['Error']['Code'])

    try:
        response = iot_client.register_certificate_without_ca(
            certificatePem=certificate_text.decode('ascii'),
            status='ACTIVE')
        return response.get("certificateId")
    except botocore.exceptions.ClientError as e:
        if e.response['Error']['Code'] == 'ThrottlingException':
            print("ERROR: ThrottlingException. Requeue for processing.")
            requeue_cb(config)
        if e.response['Error']['Code'] == 'UnauthorizedException':
            print("ERROR: There is a deployment problem with the attached"
                  "Role. Unable to reach IoT Core object.")
        return None

def process_thing_group(thing_group_arn, thing_arn):
    """Attaches the configured thing group to the iot thing"""
    if thing_group_arn is None:
        return
    iot_client = boto3client('iot')
    try:
        iot_client.add_thing_to_thing_group(thingGroupArn=thing_group_arn,
                                            thingArn=thing_arn,
                                            overrideDynamicGroups=False)
    except ClientError as error:
        raise error

def process_sqs(config):
    """Main processing function to procedurally run through processing steps."""
    certificate_id = process_certificate(config, requeue)
    process_thing(config.get('thing'),
                  certificate_id,
                  config.get('thing_type_arn'))
    process_policy(config.get('policy_arn'),
                   certificate_id)
    process_thing_group(config.get('thing_group_arn'),
                        config.get('thing'))

def lambda_handler(event: SQSEvent,
                   context: LambdaContext) -> dict: # pylint: disable=unused-argument
    """Lambda function main entry point"""
    for record in event['Records']:
        if record.get('eventSource') == 'aws:sqs':
            config = json.loads(record["body"])
            process_sqs(config)

    return event

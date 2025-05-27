"""
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

Lambda function to import certificate, construct IoT Thing, and associate
the Thing, Policy, Certificate, Thing Type, and Thing Group
"""
import ast
import base64
import json
import binascii
import os
import logging
import botocore
from botocore.exceptions import ClientError
from boto3 import client as boto3client
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.utilities.data_classes import SQSEvent

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
        error_message = error.response['Error']['Message'] # pylint: disable=unused-variable
        if error_code == 'ResourceNotFoundException':
            logger.error("get_certificate_arn failed: {error_message}")
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
#TODO: change this method to get_policy_arn
#TODO: move this to common module for providers to verify arn once
def get_policy(policy_name):
    """Retrieve the IoT policy ARN"""
    iot_client = boto3client('iot')
    try:
        response = iot_client.get_policy(policyName=policy_name)
        return response.get('policyArn')
    except ClientError as error:
        error_code = error.response['Error']['Code']
        if error_code == 'ResourceNotFoundException':
            logger.error("ERROR: You need to configure the policy {policy_name} "
                         "in your target region first.")
        if error_code == 'UnauthorizedException':
            logger.error("There is a deployment problem with the attached Role."
                  "Unable to reach IoT Core object.")
        return None
#TODO: change this method to get_thing_group_arn
#TODO: move this to common module for providers to verify arn once
def get_thing_group(thing_group_name):
    """Retrieves the thing group ARN"""
    iot_client = boto3client('iot')

    try:
        response = iot_client.describe_thing_group(thingGroupName=thing_group_name)
        return response.get('thingGroupArn')
    except ClientError as error:
        error_code = error.response['Error']['Code']
        if 'ResourceNotFoundException' == error_code:
            logger.error("You need to configure the Thing Group {thing_group_name} "
                         "in your target region first.")
        if 'UnauthorizedException' == error_code:
            logger.error("There is a deployment problem with the attached Role. Unable"
                         "to reach IoT Core object.")
        return None
#TODO: change this method to get_thing_type_arn
#TODO: move this to common module for providers to verify arn once
def get_thing_type(type_name: str) -> str:
    """Retrieves the thing type ARN"""
    iot_client = boto3client('iot')
    try:
        response = iot_client.describe_thing_type(thingTypeName=type_name)
        return response.get('thingTypeArn')
    except ClientError as error:
        error_code = error.response['Error']['Code']
        if 'ResourceNotFoundException' == error_code:
            logger.error("You need to configure the Thing Type {type_name} "
                         "in your target region first.")
        if 'UnauthorizedException' == error_code:
            logger.error("There is a deployment problem with the attached Role."
                         "Unable to reach IoT Core object.")
        return None

def process_policy(policy_name, certificate_id):
    """Attaches the IoT policy to the certificate"""
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

# TODO: shift this to common fingerprint handling code
def get_certificate_fingerprint(certificate: x509.Certificate):
    """Retrieve the certificate fingerprint"""
    return binascii.hexlify(certificate.fingerprint(hashes.SHA256())).decode('UTF-8')

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

def process_thing_group(thing_group_name, thing_name):
    """Attaches the configured thing group to the iot thing"""
    iot_client = boto3client('iot')
    try:
        thing_group_arn = get_thing_group(thing_group_name)
        thing_arn = get_thing(thing_name)
        iot_client.add_thing_to_thing_group(thingGroupName=thing_group_name,
                                            thingGroupArn=thing_group_arn,
                                            thingName=thing_name,
                                            thingArn=thing_arn,
                                            overrideDynamicGroups=False)
    except ClientError as error:
        raise error

def get_name_from_certificate(certificate_id):
    """Assume the certificate cn is the thing name.
       TODO: Evaluate for deprecation, thing name identifier better
             evaluated in the vendor specific provider.
    """
    iot_client = boto3client('iot')
    response = iot_client.describe_certificate(certificateId=certificate_id)
    certificate_text = response["certificateDescription"].get("certificatePem")
    certificate_obj = x509.load_pem_x509_certificate(data=certificate_text.encode('ascii'),
                                                     backend=default_backend())
    cn = certificate_obj.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value
    cn.replace(" ", "")
    # TODO: This must be really old because thing name is prescribed to the
    #       sqs message from the beginning, this might be eliminated
    logger.info("Certificate common name [%s] to be IoT Thing name", cn)
    return cn

def process_sqs(config):
    """Main processing function to procedurally run through processing steps."""
    policy_name = config.get('policy_name')
    thing_group_name = config.get('thing_group_name')
    thing_type_name = config.get('thing_type_name')

    certificate_id = process_certificate(config, requeue)

    if certificate_id is None:
        thing_name = config['thing']
    else:
        thing_name = get_name_from_certificate(certificate_id)

    process_thing(thing_name, certificate_id, thing_type_name)
    process_policy(policy_name, certificate_id)
    process_thing_group(thing_group_name, thing_name)

def lambda_handler(event: SQSEvent, context: LambdaContext) -> dict: # pylint: disable=unused-argument
    """Lambda function main entry point"""
    if event.get('Records') is None:
        print("ERROR: Configuration incorrect: no event record on invoke")
        return {
            "statusCode": 400,
            "body": json.dumps({
                "message": "No SQS event records available for processing."
            })
        }

    for record in event['Records']:
        if record.get('eventSource') == 'aws:sqs':
            config = json.loads(record["body"])
            process_sqs(config)

    return event

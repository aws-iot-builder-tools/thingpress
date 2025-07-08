"""
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

AWS related functions that multiple lambda functions use, here to reduce redundancy
"""
import logging
import inspect
from io import BytesIO, StringIO
from json import dumps
from botocore.exceptions import ClientError
from boto3 import client as boto3client
from boto3 import resource as boto3resource

from .circuit_state import circuit_is_open, reset_circuit, record_failure
from .circuit_state import CircuitOpenError, with_circuit_breaker

logger = logging.getLogger()
logger.setLevel("INFO")

@with_circuit_breaker('s3_download_fileobj')
def s3_object(bucket_name: str, object_name: str, fs=BytesIO()):
    """Retrieve an s3 object and return as file-like object.
       By default, it returns a byte-like object."""
    s3res = boto3resource('s3')
    res = s3res.Object(bucket_name=bucket_name, key=object_name)
    try:
        res.download_fileobj(fs)
        return fs
    except ClientError as error:
        error_code = boto_errorcode(error)
        error_mesg = boto_errormessage(error)
        this = inspect.stack()[1][3]
        logger.error("%s (bucket: %s, object: %s): %s : %s",
                     this, bucket_name, object_name, error_code, error_mesg)
        raise error

@with_circuit_breaker('s3_object_bytes')
def s3_object_bytes(bucket_name: str, object_name: str, getvalue: bool=False):
    """Download an S3 object as byte file-like object"""
    fs = BytesIO()
    s3_object(bucket_name, object_name, fs)
    if getvalue is True:
        return fs.getvalue()
    return BytesIO(fs.getvalue())

@with_circuit_breaker('sqs_send_message')
def send_sqs_message(config, queue_url):
    """Send the thing name and certificate to sqs queue"""
    sqs_client = boto3client('sqs')
    try:
        message_body = dumps(config)
        response = sqs_client.send_message(QueueUrl=queue_url, MessageBody=message_body)
        return response
    except ClientError as error:
        error_code = boto_errorcode(error)
        error_mesg = boto_errormessage(error)
        this = inspect.stack()[1][3]
        logger.error("%s %s: %s : %s", this, queue_url, error_code, error_mesg)
        raise error

@with_circuit_breaker('sqs_get_queue_attributes')
def verify_queue(queue_url: str) -> bool:
    """Verify the queue exists by attempting to fetch its attributes"""
    s = boto3client(service_name='sqs')
    try:
        s.get_queue_attributes(QueueUrl=queue_url,
                               AttributeNames=['CreatedTimestamp'])
    except ClientError as error:
        error_code = boto_errorcode(error)
        error_mesg = boto_errormessage(error)
        this = inspect.stack()[1][3]
        logger.error("%s %s: %s : %s", this, queue_url, error_code, error_mesg)
        raise error
    return True

def get_thing_group_arn(thing_group_name: str) -> str:
    """Retrieves the thing group ARN with circuit breaker pattern"""
    if thing_group_name in ("None", ""):
        raise ValueError("Nicht gut")

    operation_name = "iot_describe_thing_group"

    # Check if circuit is open
    if circuit_is_open(operation_name):
        logger.warning("Circuit breaker open for %s, failing fast", operation_name)
        raise CircuitOpenError(f"Circuit breaker open for {operation_name}")

    iot_client = boto3client('iot')
    try:
        response = iot_client.describe_thing_group(thingGroupName=thing_group_name)
        # Success - reset the circuit
        reset_circuit(operation_name)
        return response.get('thingGroupArn')
    except ClientError as error:
        # Record the failure for circuit breaker
        record_failure(operation_name)
        error_code = boto_errorcode(error)
        error_mesg = boto_errormessage(error)
        this = inspect.stack()[1][3]
        logger.error("(%s %s): %s : %s", this, thing_group_name, error_code, error_mesg)
        raise error

@with_circuit_breaker('iot_describe_thing_type')
def get_thing_type_arn(type_name: str) -> str:
    """Retrieves the thing type ARN"""
    if type_name in ("None", ""):
        raise ValueError("Nicht gut")

    iot_client = boto3client('iot')
    try:
        response = iot_client.describe_thing_type(thingTypeName=type_name)
        return response.get('thingTypeArn')
    except ClientError as error:
        error_code = boto_errorcode(error)
        error_mesg = boto_errormessage(error)
        this = inspect.stack()[1][3]
        logger.error("(%s %s): %s : %s", this, type_name, error_code, error_mesg)
        raise error

@with_circuit_breaker('iot_get_policy')
def get_policy_arn(policy_name: str) -> str:

    """Retrieve the IoT policy ARN"""
    if policy_name in ("None", ""):
        raise ValueError("Nicht gut")

    iot_client = boto3client('iot')
    try:
        response = iot_client.get_policy(policyName=policy_name)
        return response.get('policyArn')
    except ClientError as error:
        error_code = boto_errorcode(error)
        error_mesg = boto_errormessage(error)
        this = inspect.stack()[1][3]
        logger.error("(%s %s): %s : %s", this, policy_name, error_code, error_mesg)
        raise error

@with_circuit_breaker('s3_object_str')
def s3_object_str(bucket_name: str, object_name: str, getvalue: bool=False):
    """Download an S3 object as string file-like object"""
    fs = StringIO()
    s3_object(bucket_name, object_name, fs)
    if getvalue is True:
        return fs.getvalue()
    return StringIO(fs.getvalue())

def check_cfn_prop_valid(value: str) -> bool:
    """ An optional cfn prop can be empty string or 'None'. If either of these,
        return False. Otherwise True. """
    if value in ("None", ""):
        return False
    return True

def boto_errorcode(e: ClientError) -> str:
    """ Consolidate checks on typed dict having optional keys """
    if 'Error' in e.response:
        if 'Code' in e.response['Error']:
            return e.response['Error']['Code']
    return "ERROR"

def boto_errormessage(e: ClientError) -> str:
    """ Consolidate checks on typed dict having optional keys """
    if 'Error' in e.response:
        if 'Message' in e.response['Error']:
            return e.response['Error']['Message']
    return "ERROR"

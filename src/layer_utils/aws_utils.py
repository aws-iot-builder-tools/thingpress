"""
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

AWS related functions that multiple lambda functions use, here to reduce redundancy
"""
from logging import getLogger
from inspect import stack
from io import BytesIO
from json import dumps
from boto3 import Session
from botocore.exceptions import ClientError
from botocore.config import Config
from .circuit_state import circuit_is_open, reset_circuit, record_failure
from .circuit_state import CircuitOpenError, with_circuit_breaker

logger = getLogger()
logger.setLevel("INFO")

client_cache: dict = {}
default_session: Session = Session()

def client_config():
    """ Default configuration for each boto3 client """
    return Config(
        retries = {
            'max_attempts': 3,
            'mode': 'standard'
        }
    )

@with_circuit_breaker('s3_download_fileobj')
def s3_object(bucket_name: str, object_name: str, fs=BytesIO(), session: Session=default_session):
    """Retrieve an s3 object and return as file-like object.
       By default, it returns a byte-like object."""
    s3res = session.resource('s3')
    res = s3res.Object(bucket_name=bucket_name, key=object_name)
    try:
        res.download_fileobj(fs)
        return fs
    except ClientError as error:
        boto_exception(error, f"With s3 object [{object_name}] bucket [{bucket_name}]")
        raise error

@with_circuit_breaker('s3_object_bytes')
def s3_object_bytes(bucket_name: str, object_name: str, getvalue: bool=False, session: Session=default_session) -> bytes | BytesIO:
    """Download an S3 object as byte file-like object"""
    fs = BytesIO()
    s3_object(bucket_name, object_name, fs, session)
    if getvalue is True:
        return fs.getvalue()
    return BytesIO(fs.getvalue())

@with_circuit_breaker('sqs_send_message')
def send_sqs_message(config, queue_url, session: Session=default_session):
    """Send the thing name and certificate to sqs queue"""
    sqs_client = session.client('sqs')

    try:
        message_body = dumps(config)
        response = sqs_client.send_message(QueueUrl=queue_url,
                                           MessageBody=message_body)
        return response
    except ClientError as error:
        boto_exception(error, "With queue_url [{queue_url}]")
        raise error

@with_circuit_breaker('sqs_get_queue_attributes')
def verify_queue(queue_url: str, session: Session=default_session) -> bool:
    """Verify the queue exists by attempting to fetch its attributes"""
    sqs_client =  session.client('sqs')
    try:
        sqs_client.get_queue_attributes(QueueUrl=queue_url,
                                        AttributeNames=['CreatedTimestamp'])
    except ClientError as error:
        boto_exception(error, f"With queue_url [{queue_url}]")
        raise error
    return True

def get_certificate(certificate_id: str, session: Session=default_session) -> str:
    """ Verifies that the certificate is in IoT Core """
    iot_client = session.client('iot')

    try:
        response = iot_client.describe_certificate(certificateId=certificate_id)
        return response["certificateDescription"].get("certificateId")
    except ClientError as error:
        boto_exception(error, f"error on finding certificate_id {certificate_id}")
        raise error

def get_certificate_arn(certificate_id: str, session: Session=default_session) -> str:
    """ Retrieve the certificate Arn. """
    iot_client = session.client('iot')

    try:
        response = iot_client.describe_certificate(certificateId=certificate_id)
        return response["certificateDescription"].get("certificateArn")
    except ClientError as error:
        boto_exception(error, f"get_certificate_arn failed on certificate_id {certificate_id}")
        raise error

def register_certificate(certificate: str, session: Session=default_session) -> str:
    """ Register an AWS IoT certificate without a registered CA """
    iot_client = session.client('iot')
    try:
        response = iot_client.register_certificate_without_ca(
            certificatePem=certificate,
            status='ACTIVE')
        return response.get("certificateId")
    except ClientError as error:
        boto_exception(error, f"get_certificate_arn failed on certificate {certificate}")
        raise

def get_thing_group_arn(thing_group_name: str, session: Session=default_session) -> str:
    """ Retrieves the thing group ARN with circuit breaker pattern """
    if thing_group_name in ("None", ""):
        raise ValueError("The provided thing group name signals no thing group used")

    operation_name = "iot_describe_thing_group"

    # Check if circuit is open
    if circuit_is_open(operation_name):
        logger.warning("Circuit breaker open for %s, failing fast", operation_name)
        raise CircuitOpenError(f"Circuit breaker open for {operation_name}")

    iot_client = session.client('iot')
    try:
        response = iot_client.describe_thing_group(thingGroupName=thing_group_name)
        # Success - reset the circuit
        reset_circuit(operation_name)
        return response.get('thingGroupArn')
    except ClientError as error:
        # Record the failure for circuit breaker
        record_failure(operation_name)
        boto_exception(error, f"With thing group [{thing_group_name}]")
        raise error

@with_circuit_breaker('iot_describe_thing_type')
def get_thing_type_arn(type_name: str, session: Session=default_session) -> str:
    """Retrieves the thing type ARN"""
    if type_name in ("None", ""):
        raise ValueError("The thing type value signals that no thing type defined")

    iot_client = session.client('iot')
    try:
        response = iot_client.describe_thing_type(thingTypeName=type_name)
        return response.get('thingTypeArn')
    except ClientError as error:
        boto_exception(error, f"With thing type name [{type_name}]")
        raise error

@with_circuit_breaker('iot_get_policy')
def get_policy_arn(policy_name: str,
                   session: Session=default_session) -> str:

    """Retrieve the IoT policy ARN"""
    if not check_cfn_prop_valid(policy_name):
        raise ValueError("Policy name signals policy not defined")

    iot_client = session.client('iot')

    try:
        response = iot_client.get_policy(policyName=policy_name)
        return response.get('policyArn')
    except ClientError as error:
        boto_exception(error, f"With policy name [{policy_name}]")
        raise error

@with_circuit_breaker('process_iot_thing_group')
def process_thing_group(thing_group_arn: str,
                        thing_arn: str,
                        session: Session=default_session) -> None:
    """ Attaches the configured thing group to the iot thing """
    if thing_group_arn is None:
        return
    iot_client = session.client('iot')
    try:
        iot_client.add_thing_to_thing_group(thingGroupArn=thing_group_arn,
                                            thingArn=thing_arn,
                                            overrideDynamicGroups=False)
    except ClientError as error:
        boto_exception(error, f"Thing {thing_arn} attachment to thing group {thing_group_arn} creation failed")
        raise error

def process_policy(policy_name: str,
                   certificate_arn: str,
                   session: Session=default_session) -> None:
    """ Attaches the IoT policy to the certificate """
    if policy_name is None:
        return
    iot_client = session.client('iot')
    iot_client.attach_policy(policyName=policy_name, target=certificate_arn)

def process_thing(thing_name, certificate_id, session: Session=Session()) -> None:
    """Creates the IoT Thing if it does not already exist"""
    logger.info("Processing thing %s.", thing_name)
    iot_client = session.client('iot')
    certificate_arn = get_certificate_arn(certificate_id, session)
    try:
        iot_client.describe_thing(thingName=thing_name)
        return
    except ClientError as err_describe:
        boto_exception(err_describe, f"Thing {thing_name} not found. Creating.")
        try:
            iot_client.create_thing(thingName=thing_name)
        except ClientError as err_create:
            boto_exception(err_create, f"Thing {thing_name} creation failed")
            raise err_create

    try:
        iot_client.attach_thing_principal(thingName=thing_name,
                                          principal=certificate_arn)
    except ClientError as error:
        boto_exception(error, "Certificate attachment failed")
        raise error

def process_thing_type(thing_name: str,
                       thing_type_name: str,
                       session: Session=default_session) -> None:
    """ Process the thing type request which applies the thing type to the iot thing """
    iot_client = session.client('iot')

    if thing_type_name is not None:
        try:
            logger.info("Upating thing %s to apply thing type %s.",
                        thing_name,
                        thing_type_name)
            iot_client.update_thing(thingName=thing_name,
                                    thingTypeName=thing_type_name,
                                    removeThingType=False)
            return
        except ClientError as error:
            boto_exception(error, f"Thing type {thing_type_name} not found")
            raise error

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
    return "ERROR_UNKNOWN"

def boto_errormessage(e: ClientError) -> str:
    """ Consolidate checks on typed dict having optional keys """
    if 'Error' in e.response:
        if 'Message' in e.response['Error']:
            return e.response['Error']['Message']
    return "ERROR_UNKNOWN"

def boto_exception(exc: ClientError, context_message: str) -> None:
    """ Standard error message structure for boto related exceptions """
    error_message = boto_errormessage(exc)
    error_code = boto_errorcode(exc)
    this = stack()[1][3]
    logger.error("(%s %s): %s : %s", error_code, error_message, this, context_message)

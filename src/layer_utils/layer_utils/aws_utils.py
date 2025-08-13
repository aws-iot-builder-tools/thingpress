# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""AWS related functions that multiple lambda functions use, here to reduce redundancy
"""
import time
from inspect import stack
from io import BytesIO
from os import environ
from json import dumps, JSONDecodeError
from enum import Enum
from logging import getLogger
from boto3 import Session
from botocore.config import Config
from botocore.exceptions import ClientError
from aws_lambda_powertools.utilities.idempotency.config import IdempotencyConfig
from aws_lambda_powertools.utilities.idempotency.persistence.dynamodb import \
    DynamoDBPersistenceLayer
from .circuit_state import (CircuitOpenError, circuit_is_open, record_failure, reset_circuit,
                            with_circuit_breaker)

logger = getLogger()
logger.setLevel("INFO")

client_cache: dict = {}
default_session: Session = Session()

# These enums probably deserve their own module
class ProviderMessageKey(Enum):
    """SQS message keys expected by providers"""
    OBJECT_BUCKET = 'bucket'
    OBJECT_KEY = 'key'
    THING_GROUP_ARN = 'thing_group_arn'
    THING_TYPE_NAME = 'thing_type_name'
    POLICY_NAME = 'policy_name'
class ImporterMessageKey(Enum):
    """SQS message keys expected by bulk importer"""
    CERTIFICATE = 'certificate'
    THING_NAME = 'thing'
    THING_GROUP_ARN = 'thing_group_arn'
    THING_TYPE_NAME = 'thing_type_name'
    POLICY_NAME = 'policy_name'

QUEUE_DEPTH_DELAY_VERY_HIGH: int = 2000
QUEUE_DEPTH_DELAY_HIGH = 1000
QUEUE_DEPTH_DELAY_MEDIUM = 500
QUEUE_DEPTH_DELAY_MEDIUM_LOW = 100
QUEUE_DEPTH_DELAY_LOW = 0

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
    except ClientError as error:
        boto_exception(error, f"With s3 object [{object_name}] bucket [{bucket_name}]")
        raise error
    return fs

@with_circuit_breaker('s3_object_bytes')
def s3_object_bytes(bucket_name: str,
                    object_name: str,
                    getvalue: bool=False,
                    session: Session=default_session) -> bytes | BytesIO:
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
    except JSONDecodeError as e:
        logger.error("Unexpected problem loading config file:\n%s", config)
        raise e

    try:
        response = sqs_client.send_message(QueueUrl=queue_url,
                                           MessageBody=message_body)
    except ClientError as error:
        boto_exception(error, "With queue_url [{queue_url}]")
        raise error
    return response

def send_sqs_message_batch_prepare(batch_number, batch):
    """Helper for send_sqs_message_batch
       Organizes a message batch. """
    entries = []
    for idx, message in enumerate(batch):

        entry_id = str(batch_number + idx)
        entries.append({
            'Id': entry_id,
            'MessageBody': dumps(message),
            'MessageAttributes': {
                'BatchIndex': {
                    'StringValue': entry_id,
                    'DataType': 'Number'
                }
            }
        })
    return entries

@with_circuit_breaker('sqs_send_message_batch')
def send_sqs_message_batch(messages: list, queue_url: str, session: Session=default_session):
    """Send multiple messages in a single SQS batch operation

    Args:
        messages: List of message dictionaries to send
        queue_url: SQS queue URL
        session: Boto3 session

    Returns:
        List of SQS batch response dictionaries

    Raises:
        ClientError: If SQS batch operation fails
    """
    sqs_client = session.client('sqs')
    batch_size = 10  # SQS batch limit
    results = []
    failed_messages = []

    logger.info("Sending %d messages in batches to queue", len(messages))

    for i in range(0, len(messages), batch_size):
        batch = messages[i:i + batch_size]
        entries = send_sqs_message_batch_prepare(i, batch)

        try:
            response = sqs_client.send_message_batch(
                QueueUrl=queue_url,
                Entries=entries
            )
        except ClientError as error:
            logger.error("SQS batch send failed for batch starting at index %d: %s", i, error)
            boto_exception(error, f"With queue_url [{queue_url}]")
            raise error

        results.append(response)

        # Log successful sends
        if 'Successful' in response:
            logger.info("Successfully sent %d messages in batch", len(response['Successful']))

        # Handle partial failures
        if 'Failed' in response and response['Failed']:
            logger.warning(
                "Batch send partial failure: %d messages failed",
                len(response['Failed'])
                )

            for failure in response['Failed']:
                failed_msg_idx = int(failure['Id'])
                failed_messages.append({
                    'message': messages[failed_msg_idx],
                    'error': failure,
                    'batch_index': failed_msg_idx
                })

                logger.error(
                    "Failed to send message %s: %s - %s",
                    failure['Id'],
                    failure['Code'],
                    failure['Message']
                    )

    # Report final statistics
    logger.info("Batch send complete: %d sent, %d failed",
                sum(len(r.get('Successful', [])) for r in results),
                len(failed_messages))

    if failed_messages:
        logger.warning("Failed messages details logged for retry")

    return results

@with_circuit_breaker('sqs_send_message_batch_with_retry')
def send_sqs_message_batch_with_retry(messages: list, queue_url: str,
                                    session: Session=default_session, max_retries: int = 3):
    """
    Send messages in batches with retry logic for failed messages

    Args:
        messages: List of message dictionaries to send
        queue_url: SQS queue URL
        session: Boto3 session
        max_retries: Maximum number of retry attempts

    Returns:
        List of SQS batch response dictionaries
    """
    remaining_messages = messages.copy()
    all_results = []

    for attempt in range(max_retries):
        if not remaining_messages:
            break

        logger.info(
            "Batch send attempt %d/%d for %d messages",
            attempt + 1,
            max_retries,
            len(remaining_messages)
            )

        try:
            results = send_sqs_message_batch(remaining_messages, queue_url, session)
        except ClientError as error:
            if attempt == max_retries - 1:
                logger.error("Final retry attempt failed: %s", error)
                raise error
            sleep_time = 2 ** attempt
            logger.warning(
                "Retry attempt %d failed, waiting %ds: %s",
                attempt + 1,
                sleep_time,
                error
            )
            time.sleep(sleep_time)
            continue

        all_results.extend(results)

        # Collect failed messages for retry
        failed_messages = []
        for result in results:
            if not 'Failed' in result:
                break
            for failure in result['Failed']:
                failed_msg_idx = int(failure['Id'])
                if failed_msg_idx < len(remaining_messages):
                    failed_messages.append(remaining_messages[failed_msg_idx])

        remaining_messages = failed_messages

        if not remaining_messages:
            logger.info("All messages sent successfully")
            break
        if attempt < max_retries - 1:
            # Exponential backoff
            sleep_time = 2 ** attempt
            logger.info(
                "Retrying %d failed messages after %ds delay",
                len(remaining_messages),
                sleep_time
            )
            time.sleep(sleep_time)

    if remaining_messages:
        logger.error(
            "Failed to send %d messages after %d attempts",
            len(remaining_messages),
            max_retries
        )

    return all_results

def get_queue_depth(queue_url: str, session: Session = default_session) -> dict:
    """Get current queue depth metrics for throttling decisions

    Args:
        queue_url: SQS queue URL
        session: Boto3 session

    Returns:
        Dictionary with queue depth metrics
    """
    sqs_client = session.client('sqs')

    try:
        response = sqs_client.get_queue_attributes(
            QueueUrl=queue_url,
            AttributeNames=[
                'ApproximateNumberOfMessages',
                'ApproximateNumberOfMessagesNotVisible',
                'ApproximateNumberOfMessagesDelayed'
            ]
        )
    except ClientError as error:
        logger.error("Failed to get queue attributes for %s: %s", queue_url, error)
        boto_exception(error, f"With queue_url [{queue_url}]")
        raise error

    attrs = response['Attributes']

    visible = int(attrs.get('ApproximateNumberOfMessages', 0))
    in_flight = int(attrs.get('ApproximateNumberOfMessagesNotVisible', 0))
    delayed = int(attrs.get('ApproximateNumberOfMessagesDelayed', 0))
    total = visible + in_flight

    return {
        'visible': visible,
        'in_flight': in_flight,
        'delayed': delayed,
        'total': total,
        'queue_url': queue_url
    }


def calculate_optimal_delay(queue_depth: int, base_delay: int = 30) -> int:
    """Calculate optimal delay based on queue depth for automatic throttling

    Args:
        queue_depth: Current total queue depth
        base_delay: Base delay in seconds (default: 30)

    Returns:
        Recommended delay in seconds
    """
    if queue_depth > QUEUE_DEPTH_DELAY_VERY_HIGH:
        return base_delay * 4  # 2 minutes for very high load
    if queue_depth > QUEUE_DEPTH_DELAY_HIGH:
        return base_delay * 2  # 1 minute for high load
    if queue_depth > QUEUE_DEPTH_DELAY_MEDIUM:
        return base_delay      # 30 seconds for medium load
    if queue_depth > QUEUE_DEPTH_DELAY_MEDIUM_LOW:
        return base_delay // 2 # 15 seconds for low-medium load

    return 0               # No delay for low load

def send_sqs_message_with_throttling(messages: list, queue_url: str,
                                   session: Session = default_session,
                                   enable_throttling: bool = True,
                                   base_delay: int = 30) -> list:
    """Send messages with automatic throttling based on queue depth

    Args:
        messages: List of message dictionaries to send
        queue_url: SQS queue URL
        session: Boto3 session
        enable_throttling: Whether to enable automatic throttling
        base_delay: Base delay for throttling calculations

    Returns:
        List of SQS batch response dictionaries
    """
    if enable_throttling:
        try:
            # Check queue depth and calculate delay
            queue_metrics = get_queue_depth(queue_url, session)
        except ClientError as e:
            # If throttling check fails, continue without throttling
            boto_exception(e, "Throttling check failed, proceeding without delay")
            queue_metrics = None

        if queue_metrics:
            delay = calculate_optimal_delay(queue_metrics['total'], base_delay)

            logger.info("Queue throttling check: depth=%d, delay=%ds",
                        queue_metrics['total'], delay)

            if delay > 0:
                logger.info(
                    "Throttling: waiting %d seconds before sending %d messages",
                    delay,
                    len(messages)
                )
                time.sleep(delay)

    # Send messages in batches with retry
    return send_sqs_message_batch_with_retry(messages, queue_url, session)

def send_sqs_message_with_adaptive_throttling(messages: list, queue_url: str,
                                            session: Session = default_session,
                                            max_queue_depth: int = 1000,
                                            check_interval: int = 10) -> list:
    """
    Send messages with adaptive throttling that monitors queue depth during processing

    Args:
        messages: List of message dictionaries to send
        queue_url: SQS queue URL
        session: Boto3 session
        max_queue_depth: Maximum allowed queue depth before throttling
        check_interval: Number of batches between queue depth checks

    Returns:
        List of SQS batch response dictionaries
    """
    batch_size = 10  # SQS batch limit
    all_results = []

    logger.info("Starting adaptive throttling send for %d messages", len(messages))

    for i in range(0, len(messages), batch_size):
        batch = messages[i:i + batch_size]
        batch_num = (i // batch_size) + 1

        # Check queue depth periodically
        if batch_num % check_interval == 1:  # Check on first batch and every check_interval batches
            try:
                queue_metrics = get_queue_depth(queue_url, session)
            except ClientError as e:
                boto_exception(e, f"Adaptive throttling check failed for batch {batch_num}")

            current_depth = queue_metrics['total']

            logger.info(
                "Adaptive throttling check (batch %d): queue_depth=%d",
                batch_num,
                current_depth
            )

            if current_depth > max_queue_depth:
                # Calculate adaptive delay based on how far over the limit we are
                excess_ratio = current_depth / max_queue_depth
                # Cap at 60 seconds
                adaptive_delay = min(60, int(30 * excess_ratio))

                logger.info("Queue depth (%d) exceeds limit (%d), waiting %ds",
                            current_depth, max_queue_depth, adaptive_delay)
                time.sleep(adaptive_delay)

        # Send the batch
        try:
            batch_results = send_sqs_message_batch_with_retry([batch], queue_url, session)
        except ClientError as e:
            boto_exception(e, f"Failed to send batch {batch_num}")
            raise e
        all_results.extend(batch_results)

        # Small delay between batches to avoid overwhelming
        if i + batch_size < len(messages):
            time.sleep(0.1)  # 100ms between batches

    logger.info("Adaptive throttling send completed: %d batch responses", len(all_results))
    return all_results

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
    except ClientError as error:
        boto_exception(error, f"error on finding certificate_id {certificate_id}")
        raise error
    return response["certificateDescription"].get("certificateId")

def get_certificate_arn(certificate_id: str, session: Session=default_session) -> str:
    """ Retrieve the certificate Arn. """
    iot_client = session.client('iot')

    try:
        response = iot_client.describe_certificate(certificateId=certificate_id)
    except ClientError as error:
        boto_exception(error, f"get_certificate_arn failed on certificate_id {certificate_id}")
        raise error
    return response["certificateDescription"].get("certificateArn")

def register_certificate(certificate: str,
                         session: Session=default_session) -> str:
    """ Register an AWS IoT certificate without a registered CA 

    Args:
        certificate: The certificate PEM string
        session: Boto3 session (when tags are provided)

    Returns:
        Certificate ID
    """
    iot_client = session.client('iot')
    try:
        # Register the certificate
        response = iot_client.register_certificate_without_ca(
            certificatePem=certificate,
            status='ACTIVE')
    except ClientError as error:
        boto_exception(error, f"register_certificate failed on certificate {certificate}")
        raise
    certificate_id = response.get("certificateId")

    return certificate_id

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
    except ClientError as error:
        # Record the failure for circuit breaker
        record_failure(operation_name)
        boto_exception(error, f"With thing group [{thing_group_name}]")
        raise error
    # Success - reset the circuit
    reset_circuit(operation_name)
    return response.get('thingGroupArn')

@with_circuit_breaker('iot_describe_thing_type')
def get_thing_type_arn(type_name: str, session: Session=default_session) -> str:
    """Retrieves the thing type ARN"""
    if type_name in ("None", ""):
        raise ValueError("The thing type value signals that no thing type defined")

    iot_client = session.client('iot')
    try:
        response = iot_client.describe_thing_type(thingTypeName=type_name)
    except ClientError as error:
        boto_exception(error, f"With thing type name [{type_name}]")
        raise error
    return response.get('thingTypeArn')

@with_circuit_breaker('iot_describe_thing')
def get_thing_arn(thing_name: str, session: Session=default_session) -> str:
    """Retrieves the thing ARN"""
    if thing_name in ("None", ""):
        raise ValueError("The thing name value signals that no thing defined")

    iot_client = session.client('iot')
    try:
        response = iot_client.describe_thing(thingName=thing_name)
    except ClientError as error:
        boto_exception(error, f"With thing name [{thing_name}]")
        raise error
    return response.get('thingArn')

@with_circuit_breaker('iot_get_policy')
def get_policy_arn(policy_name: str,
                   session: Session=default_session) -> str:

    """Retrieve the IoT policy ARN"""
    if not check_cfn_prop_valid(policy_name):
        raise ValueError("Policy name signals policy not defined")

    iot_client = session.client('iot')

    try:
        response = iot_client.get_policy(policyName=policy_name)
    except ClientError as error:
        boto_exception(error, f"With policy name [{policy_name}]")
        raise error
    return response.get('policyArn')

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
        boto_exception(
            error, f"Thing {thing_arn} attachment to thing group {thing_group_arn} creation failed")
        raise error

def process_policy(policy_name: str,
                   certificate_arn: str,
                   session: Session=default_session) -> None:
    """ Attaches the IoT policy to the certificate """
    if policy_name is None:
        return
    iot_client = session.client('iot')
    iot_client.attach_policy(policyName=policy_name, target=certificate_arn)

def process_thing(thing_name: str,
                  certificate_id: str,
                  session: Session=default_session) -> None:
    """Creates the IoT Thing if it does not already exist and attaches certificate

    Args:
        thing_name: Name of the IoT Thing to create
        certificate_id: Certificate ID to attach to the thing
        tags: Optional list of tags to apply to the thing
              Format: [{'Key': 'key1', 'Value': 'value1'}, {'Key': 'key2', 'Value': 'value2'}]
        session: Boto3 session
    """
    logger.info("Processing thing %s.", thing_name)
    iot_client = session.client('iot')
    certificate_arn = get_certificate_arn(certificate_id, session)

    try:
        iot_client.describe_thing(thingName=thing_name)
        logger.info("Thing %s already exists", thing_name)
    except ClientError as err_describe:
        boto_exception(err_describe, f"Thing {thing_name} not found. Creating.")
        try:
            iot_client.create_thing(thingName=thing_name)
        except ClientError as err_create:
            boto_exception(err_create, f"Thing {thing_name} creation failed")
            raise err_create
    logger.info("Created thing %s", thing_name)

    # Always attempt to attach certificate, whether thing existed or was just created
    try:
        principals_response = iot_client.list_thing_principals(thingName=thing_name)
    except ClientError as list_error:
        # If we can't list principals, try to attach anyway (might be a permission issue)
        logger.warning("Could not list thing principals for %s: %s."
                        "Attempting attachment anyway.",
                        thing_name, str(list_error))
        iot_client.attach_thing_principal(thingName=thing_name, principal=certificate_arn)
        logger.info("Attached certificate %s to thing %s", certificate_id, thing_name)

    attached_principals = principals_response.get('principals', [])

    if certificate_arn in attached_principals:
        logger.info("Certificate %s already attached to thing %s",
                    certificate_id, thing_name)
        return

    try:
        iot_client.attach_thing_principal(thingName=thing_name, principal=certificate_arn)
    except ClientError as error:
        if boto_errorcode(error) == 'ResourceAlreadyExistsException':
            logger.info("Certificate %s already attached to thing %s", certificate_id, thing_name)
        else:
            boto_exception(error, f"Certificate attachment failed for thing {thing_name}")
            raise error

    logger.info("Attached certificate %s to thing %s", certificate_id, thing_name)

def process_thing_type(thing_name: str,
                       thing_type_name: str|None,
                       session: Session=default_session) -> None:
    """ Process the thing type request which applies the thing type to the iot thing """
    iot_client = session.client('iot')

    if thing_type_name is None:
        return

    logger.info("Upating thing %s to apply thing type %s.",
                thing_name,
                thing_type_name)
    try:
        iot_client.update_thing(thingName=thing_name,
                                thingTypeName=thing_type_name,
                                removeThingType=False)
    except ClientError as error:
        boto_exception(error, f"Thing type {thing_type_name} not found")
        raise error

def powertools_idempotency_environ():
    """sets powertools adjustments for idempotency functionality"""
    if environ.get("POWERTOOLS_IDEMPOTENCY_TABLE") is None:
        raise ValueError("Environment variable POWERTOOLS_IDEMPOTENCY_TABLE not set.")

    powertools_idempotency_table: str = environ["POWERTOOLS_IDEMPOTENCY_TABLE"]

    if environ.get("POWERTOOLS_IDEMPOTENCY_EXPIRY_SECONDS") is None:
        powertools_idempotency_expiry_seconds: int = 3600
    else:
        powertools_idempotency_expiry_seconds: int = int(
            environ.get("POWERTOOLS_IDEMPOTENCY_EXPIRY_SECONDS", 3600))

    # Initialize persistence layer for idempotency
    persistence_layer = DynamoDBPersistenceLayer(
        table_name=powertools_idempotency_table,
        key_attr="id",
        expiry_attr="expiration",
        status_attr="status",
        data_attr="data",
        validation_key_attr="validation"
    )

    # Configure idempotency with jitter for high-volume processing
    idempotency_config = IdempotencyConfig(
        # Use jitter_key_generator for jitter instead of event_key_jitter
        expires_after_seconds=powertools_idempotency_expiry_seconds
    )
    return persistence_layer, idempotency_config

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

def check_cfn_prop_valid(value: str) -> bool:
    """ An optional cfn prop can be empty string or 'None'. If either of these,
        return False. Otherwise True. """
    return value not in ("None", "", None)

#!/usr/bin/env python3
"""
Enhanced AWS Utils with SQS Batch Optimization
This shows how to modify the existing aws_utils.py to support batch operations
"""

import time
import logging
from json import dumps
from typing import List, Dict, Any, Optional
from boto3 import Session
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

# Existing circuit breaker decorator (placeholder)
def with_circuit_breaker(name):
    def decorator(func):
        return func
    return decorator

@with_circuit_breaker('sqs_send_message_batch')
def send_sqs_message_batch(messages: List[Dict], queue_url: str, session: Session = None) -> List[Dict]:
    """
    Send multiple messages in a single SQS batch operation
    
    Args:
        messages: List of message dictionaries to send
        queue_url: SQS queue URL
        session: Boto3 session (optional)
    
    Returns:
        List of SQS batch response dictionaries
    
    Raises:
        ClientError: If SQS batch operation fails
    """
    if session is None:
        session = Session()
    
    sqs_client = session.client('sqs')
    batch_size = 10  # SQS batch limit
    results = []
    failed_messages = []
    
    logger.info(f"Sending {len(messages)} messages in batches to {queue_url}")
    
    for i in range(0, len(messages), batch_size):
        batch = messages[i:i + batch_size]
        entries = []
        
        # Prepare batch entries
        for idx, message in enumerate(batch):
            entry_id = str(i + idx)
            entries.append({
                'Id': entry_id,
                'MessageBody': dumps(message),
                'MessageAttributes': {
                    'BatchIndex': {
                        'StringValue': entry_id,
                        'DataType': 'Number'
                    },
                    'Timestamp': {
                        'StringValue': str(int(time.time())),
                        'DataType': 'Number'
                    }
                }
            })
        
        try:
            response = sqs_client.send_message_batch(
                QueueUrl=queue_url,
                Entries=entries
            )
            
            results.append(response)
            
            # Log successful sends
            if 'Successful' in response:
                logger.info(f"Successfully sent {len(response['Successful'])} messages in batch")
            
            # Handle partial failures
            if 'Failed' in response and response['Failed']:
                logger.warning(f"Batch send partial failure: {len(response['Failed'])} messages failed")
                
                for failure in response['Failed']:
                    failed_msg_idx = int(failure['Id'])
                    failed_messages.append({
                        'message': messages[failed_msg_idx],
                        'error': failure,
                        'batch_index': failed_msg_idx
                    })
                    
                    logger.error(f"Failed to send message {failure['Id']}: {failure['Code']} - {failure['Message']}")
            
        except ClientError as error:
            logger.error(f"SQS batch send failed for batch starting at index {i}: {error}")
            # Add all messages in this batch to failed list
            for idx, message in enumerate(batch):
                failed_messages.append({
                    'message': message,
                    'error': str(error),
                    'batch_index': i + idx
                })
            raise error
    
    # Report final statistics
    total_sent = sum(len(r.get('Successful', [])) for r in results)
    total_failed = len(failed_messages)
    
    logger.info(f"Batch send complete: {total_sent} sent, {total_failed} failed")
    
    if failed_messages:
        logger.warning(f"Failed messages: {failed_messages}")
    
    return results

@with_circuit_breaker('sqs_send_message_batch_with_retry')
def send_sqs_message_batch_with_retry(messages: List[Dict], queue_url: str, 
                                    session: Session = None, max_retries: int = 3) -> List[Dict]:
    """
    Send messages in batches with retry logic for failed messages
    
    Args:
        messages: List of message dictionaries to send
        queue_url: SQS queue URL
        session: Boto3 session (optional)
        max_retries: Maximum number of retry attempts
    
    Returns:
        List of SQS batch response dictionaries
    """
    remaining_messages = messages.copy()
    all_results = []
    
    for attempt in range(max_retries):
        if not remaining_messages:
            break
            
        logger.info(f"Batch send attempt {attempt + 1}/{max_retries} for {len(remaining_messages)} messages")
        
        try:
            results = send_sqs_message_batch(remaining_messages, queue_url, session)
            all_results.extend(results)
            
            # Collect failed messages for retry
            failed_messages = []
            for result in results:
                if 'Failed' in result and result['Failed']:
                    for failure in result['Failed']:
                        failed_msg_idx = int(failure['Id'])
                        if failed_msg_idx < len(remaining_messages):
                            failed_messages.append(remaining_messages[failed_msg_idx])
            
            remaining_messages = failed_messages
            
            if not remaining_messages:
                logger.info("All messages sent successfully")
                break
            elif attempt < max_retries - 1:
                # Exponential backoff
                sleep_time = 2 ** attempt
                logger.info(f"Retrying {len(remaining_messages)} failed messages after {sleep_time}s delay")
                time.sleep(sleep_time)
            
        except ClientError as error:
            if attempt == max_retries - 1:
                logger.error(f"Final retry attempt failed: {error}")
                raise error
            else:
                sleep_time = 2 ** attempt
                logger.warning(f"Retry attempt {attempt + 1} failed, waiting {sleep_time}s: {error}")
                time.sleep(sleep_time)
    
    if remaining_messages:
        logger.error(f"Failed to send {len(remaining_messages)} messages after {max_retries} attempts")
    
    return all_results

# Enhanced version of existing function with batch capability
@with_circuit_breaker('sqs_send_message')
def send_sqs_message(config: Dict, queue_url: str, session: Session = None) -> Dict:
    """
    Send a single message to SQS queue (backward compatibility)
    
    Args:
        config: Message configuration dictionary
        queue_url: SQS queue URL
        session: Boto3 session (optional)
    
    Returns:
        SQS response dictionary
    """
    if session is None:
        session = Session()
    
    sqs_client = session.client('sqs')
    
    try:
        message_body = dumps(config)
        response = sqs_client.send_message(
            QueueUrl=queue_url,
            MessageBody=message_body
        )
        return response
    except ClientError as error:
        logger.error(f"SQS send_message failed for queue {queue_url}: {error}")
        raise error

def get_queue_depth(queue_url: str, session: Session = None) -> Dict[str, int]:
    """
    Get current queue depth for throttling decisions
    
    Args:
        queue_url: SQS queue URL
        session: Boto3 session (optional)
    
    Returns:
        Dictionary with queue depth metrics
    """
    if session is None:
        session = Session()
    
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
        
        attrs = response['Attributes']
        
        return {
            'visible': int(attrs.get('ApproximateNumberOfMessages', 0)),
            'in_flight': int(attrs.get('ApproximateNumberOfMessagesNotVisible', 0)),
            'delayed': int(attrs.get('ApproximateNumberOfMessagesDelayed', 0)),
            'total': int(attrs.get('ApproximateNumberOfMessages', 0)) + 
                    int(attrs.get('ApproximateNumberOfMessagesNotVisible', 0))
        }
        
    except ClientError as error:
        logger.error(f"Failed to get queue attributes for {queue_url}: {error}")
        raise error

def calculate_optimal_delay(queue_depth: int, base_delay: int = 30) -> int:
    """
    Calculate optimal delay based on queue depth for automatic throttling
    
    Args:
        queue_depth: Current total queue depth
        base_delay: Base delay in seconds
    
    Returns:
        Recommended delay in seconds
    """
    if queue_depth > 1000:
        return base_delay * 2  # Double delay for high load
    elif queue_depth > 500:
        return base_delay      # Normal delay for medium load
    elif queue_depth > 100:
        return base_delay // 2 # Half delay for low-medium load
    else:
        return 0               # No delay for low load

def send_sqs_message_with_throttling(messages: List[Dict], queue_url: str, 
                                   session: Session = None, 
                                   enable_throttling: bool = True,
                                   base_delay: int = 30) -> List[Dict]:
    """
    Send messages with automatic throttling based on queue depth
    
    Args:
        messages: List of message dictionaries to send
        queue_url: SQS queue URL
        session: Boto3 session (optional)
        enable_throttling: Whether to enable automatic throttling
        base_delay: Base delay for throttling calculations
    
    Returns:
        List of SQS batch response dictionaries
    """
    if enable_throttling:
        # Check queue depth and calculate delay
        queue_metrics = get_queue_depth(queue_url, session)
        delay = calculate_optimal_delay(queue_metrics['total'], base_delay)
        
        logger.info(f"Queue depth: {queue_metrics['total']}, calculated delay: {delay}s")
        
        if delay > 0:
            logger.info(f"Throttling: waiting {delay} seconds before sending {len(messages)} messages")
            time.sleep(delay)
    
    # Send messages in batches
    return send_sqs_message_batch_with_retry(messages, queue_url, session)

# Example usage in provider functions
def process_certificates_optimized(certificates: List[str], config: Dict, 
                                 queue_url: str, session: Session = None) -> int:
    """
    Example of how to modify provider functions to use batch processing
    
    Args:
        certificates: List of base64-encoded certificates
        config: Base configuration dictionary
        queue_url: Target SQS queue URL
        session: Boto3 session (optional)
    
    Returns:
        Number of certificates processed
    """
    batch_messages = []
    batch_size = 10  # SQS batch limit
    total_processed = 0
    
    logger.info(f"Processing {len(certificates)} certificates in batches")
    
    for certificate in certificates:
        # Create certificate configuration
        cert_config = config.copy()
        cert_config['certificate'] = certificate
        
        # Extract thing name (this would use actual cert parsing)
        cert_config['thing'] = f"device-{len(batch_messages)}"  # Placeholder
        
        batch_messages.append(cert_config)
        
        # Send batch when full
        if len(batch_messages) >= batch_size:
            try:
                send_sqs_message_with_throttling(batch_messages, queue_url, session)
                total_processed += len(batch_messages)
                logger.info(f"Sent batch of {len(batch_messages)} certificates")
                batch_messages = []
            except Exception as error:
                logger.error(f"Failed to send batch: {error}")
                raise error
    
    # Send remaining messages
    if batch_messages:
        try:
            send_sqs_message_with_throttling(batch_messages, queue_url, session)
            total_processed += len(batch_messages)
            logger.info(f"Sent final batch of {len(batch_messages)} certificates")
        except Exception as error:
            logger.error(f"Failed to send final batch: {error}")
            raise error
    
    logger.info(f"Successfully processed {total_processed} certificates")
    return total_processed

if __name__ == "__main__":
    # Example usage
    print("Enhanced AWS Utils with SQS Batch Optimization")
    print("This module provides:")
    print("• send_sqs_message_batch() - Batch message sending")
    print("• send_sqs_message_batch_with_retry() - Batch sending with retry logic")
    print("• get_queue_depth() - Queue depth monitoring")
    print("• calculate_optimal_delay() - Dynamic throttling")
    print("• send_sqs_message_with_throttling() - Automatic throttling")
    print("• process_certificates_optimized() - Example provider function")

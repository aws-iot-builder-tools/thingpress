"""
AWS Helper utilities for integration testing
"""

import boto3
import json
import time
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

class AWSHelpers:
    """Helper functions for AWS service interactions"""
    
    @staticmethod
    def get_queue_url(queue_name: str, region: str = 'us-east-1') -> str:
        """Get SQS queue URL from queue name"""
        sqs = boto3.client('sqs', region_name=region)
        try:
            response = sqs.get_queue_url(QueueName=queue_name)
            return response['QueueUrl']
        except Exception as e:
            logger.error(f"Failed to get queue URL for {queue_name}: {e}")
            raise
            
    @staticmethod
    def wait_for_lambda_completion(function_name: str, request_id: str, 
                                 timeout_seconds: int = 300, region: str = 'us-east-1') -> bool:
        """Wait for Lambda function to complete by monitoring CloudWatch logs"""
        logs_client = boto3.client('logs', region_name=region)
        log_group = f"/aws/lambda/{function_name}"
        
        start_time = time.time()
        while time.time() - start_time < timeout_seconds:
            try:
                # Look for log streams
                response = logs_client.describe_log_streams(
                    logGroupName=log_group,
                    orderBy='LastEventTime',
                    descending=True,
                    limit=10
                )
                
                for stream in response['logStreams']:
                    # Check if this stream contains our request
                    events_response = logs_client.get_log_events(
                        logGroupName=log_group,
                        logStreamName=stream['logStreamName'],
                        startTime=int((time.time() - 300) * 1000)  # Last 5 minutes
                    )
                    
                    for event in events_response['events']:
                        if request_id in event['message']:
                            if 'END RequestId' in event['message']:
                                return True
                            elif 'ERROR' in event['message'] or 'FAILED' in event['message']:
                                logger.warning(f"Lambda execution may have failed: {event['message']}")
                                
            except Exception as e:
                logger.debug(f"Error checking logs: {e}")
                
            time.sleep(2)
            
        logger.warning(f"Timeout waiting for Lambda {function_name} completion")
        return False
        
    @staticmethod
    def get_recent_iot_things(minutes: int = 10, region: str = 'us-east-1') -> List[Dict]:
        """Get IoT things created in the last N minutes"""
        iot = boto3.client('iot', region_name=region)
        cutoff_time = time.time() - (minutes * 60)
        
        try:
            response = iot.list_things(maxResults=100)
            recent_things = []
            
            for thing in response.get('things', []):
                creation_date = thing.get('creationDate')
                if creation_date and creation_date.timestamp() > cutoff_time:
                    recent_things.append(thing)
                    
            return recent_things
            
        except Exception as e:
            logger.error(f"Failed to get recent IoT things: {e}")
            return []
            
    @staticmethod
    def get_thing_certificates(thing_name: str, region: str = 'us-east-1') -> List[str]:
        """Get certificates attached to an IoT thing"""
        iot = boto3.client('iot', region_name=region)
        
        try:
            response = iot.list_thing_principals(thingName=thing_name)
            return response.get('principals', [])
        except Exception as e:
            logger.error(f"Failed to get certificates for thing {thing_name}: {e}")
            return []
            
    @staticmethod
    def get_certificate_policies(certificate_arn: str, region: str = 'us-east-1') -> List[str]:
        """Get policies attached to a certificate"""
        iot = boto3.client('iot', region_name=region)
        
        try:
            response = iot.list_principal_policies(principal=certificate_arn)
            return [policy['policyName'] for policy in response.get('policies', [])]
        except Exception as e:
            logger.error(f"Failed to get policies for certificate {certificate_arn}: {e}")
            return []
            
    @staticmethod
    def verify_s3_object_exists(bucket: str, key: str, region: str = 'us-east-1') -> bool:
        """Verify an S3 object exists"""
        s3 = boto3.client('s3', region_name=region)
        
        try:
            s3.head_object(Bucket=bucket, Key=key)
            return True
        except s3.exceptions.NoSuchKey:
            return False
        except Exception as e:
            logger.error(f"Error checking S3 object s3://{bucket}/{key}: {e}")
            return False
            
    @staticmethod
    def get_sqs_queue_attributes(queue_url: str, region: str = 'us-east-1') -> Dict:
        """Get SQS queue attributes"""
        sqs = boto3.client('sqs', region_name=region)
        
        try:
            response = sqs.get_queue_attributes(
                QueueUrl=queue_url,
                AttributeNames=['All']
            )
            return response.get('Attributes', {})
        except Exception as e:
            logger.error(f"Failed to get queue attributes: {e}")
            return {}
            
    @staticmethod
    def purge_sqs_queue(queue_url: str, region: str = 'us-east-1') -> bool:
        """Purge all messages from an SQS queue"""
        sqs = boto3.client('sqs', region_name=region)
        
        try:
            sqs.purge_queue(QueueUrl=queue_url)
            logger.info(f"Purged queue: {queue_url}")
            return True
        except Exception as e:
            logger.error(f"Failed to purge queue {queue_url}: {e}")
            return False

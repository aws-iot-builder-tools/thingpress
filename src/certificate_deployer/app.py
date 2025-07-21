"""
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

Lambda function to deploy Microchip verifier certificates to S3 bucket.
"""
import base64
import json
import logging

import boto3
import cfnresponse

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def disable_bucket_notifications(bucket_name):
    """
    Disable all notifications on the S3 bucket.

    Args:
        bucket_name (str): Name of the S3 bucket

    Returns:
        dict: The previous notification configuration (for restoration)
    """
    logger.info("Disabling notifications for bucket %s", bucket_name)
    s3_client = boto3.client('s3')

    # Get the current notification configuration
    try:
        response = s3_client.get_bucket_notification_configuration(
            Bucket=bucket_name
        )

        # Store the current configuration for later restoration
        current_config = {}
        if 'LambdaFunctionConfigurations' in response:
            current_config['LambdaFunctionConfigurations'] = (
                response['LambdaFunctionConfigurations']
            )
        if 'TopicConfigurations' in response:
            current_config['TopicConfigurations'] = response['TopicConfigurations']
        if 'QueueConfigurations' in response:
            current_config['QueueConfigurations'] = response['QueueConfigurations']

        # Clear all notifications
        s3_client.put_bucket_notification_configuration(
            Bucket=bucket_name,
            NotificationConfiguration={}
        )

        logger.info("Successfully disabled notifications for bucket %s", bucket_name)
        return current_config
    except Exception as e:
        logger.error("Error disabling bucket notifications: %s", str(e))
        # Return empty config if we couldn't get the current one
        return {}

def configure_bucket_notifications(bucket_name, notification_config=None, lambda_arn=None):
    """
    Configure notifications on the S3 bucket.

    Args:
        bucket_name (str): Name of the S3 bucket
        notification_config (dict): Notification configuration to apply
        lambda_arn (str): ARN of the Lambda function for default configuration

    Returns:
        bool: True if successful, False otherwise
    """
    logger.info("Configuring notifications for bucket %s", bucket_name)
    s3_client = boto3.client('s3')

    try:
        if notification_config:
            # Transform the configuration to match S3 API expectations
            s3_config = {}

            # Handle LambdaFunctionConfigurations -> LambdaConfigurations
            if 'LambdaFunctionConfigurations' in notification_config:
                s3_config['LambdaConfigurations'] = []
                for lambda_config in notification_config['LambdaFunctionConfigurations']:
                    s3_lambda_config = {
                        'LambdaFunctionArn': lambda_config['LambdaFunctionArn'],
                        'Events': ([lambda_config['Event']]
                                 if isinstance(lambda_config['Event'], str)
                                 else lambda_config['Event'])
                    }

                    # Handle Filter configuration
                    if 'Filter' in lambda_config:
                        s3_lambda_config['Filter'] = {}
                        if 'S3Key' in lambda_config['Filter']:
                            s3_lambda_config['Filter']['Key'] = {
                                'FilterRules': []
                            }
                            for rule in lambda_config['Filter']['S3Key']['Rules']:
                                s3_lambda_config['Filter']['Key']['FilterRules'].append({
                                    'Name': rule['Name'].lower(),  # S3 API expects lowercase
                                    'Value': rule['Value']
                                })

                    s3_config['LambdaConfigurations'].append(s3_lambda_config)

            # Handle other configuration types if needed
            if 'TopicConfigurations' in notification_config:
                s3_config['TopicConfigurations'] = notification_config['TopicConfigurations']
            if 'QueueConfigurations' in notification_config:
                s3_config['QueueConfigurations'] = notification_config['QueueConfigurations']

            # Apply the transformed notification configuration
            logger.info("Applying notification configuration: %s", json.dumps(s3_config))
            s3_client.put_bucket_notification_configuration(
                Bucket=bucket_name,
                NotificationConfiguration=s3_config
            )
        elif lambda_arn:
            # Apply a default configuration with the provided Lambda ARN
            s3_client.put_bucket_notification_configuration(
                Bucket=bucket_name,
                NotificationConfiguration={
                    'LambdaConfigurations': [
                        {
                            'LambdaFunctionArn': lambda_arn,
                            'Events': ['s3:ObjectCreated:*'],
                            'Filter': {
                                'Key': {
                                    'FilterRules': [
                                        {
                                            'Name': 'suffix',
                                            'Value': '.json'
                                        }
                                    ]
                                }
                            }
                        }
                    ]
                }
            )
        else:
            # Clear all notifications
            s3_client.put_bucket_notification_configuration(
                Bucket=bucket_name,
                NotificationConfiguration={}
            )

        logger.info("Successfully configured notifications for bucket %s", bucket_name)
        return True
    except Exception as e:
        logger.error("Error configuring bucket notifications: %s", str(e))
        return False

def deploy_certificates(bucket_name, certificates):
    """
    Deploy certificates to the S3 bucket.

    Args:
        bucket_name (str): Name of the S3 bucket
        certificates (dict): Dictionary of certificate name to base64-encoded content

    Returns:
        bool: True if successful, False otherwise
    """
    logger.info("Deploying certificates to bucket %s", bucket_name)
    s3_client = boto3.client('s3')

    try:
        # Deploy each certificate to the S3 bucket
        for cert_name, cert_content in certificates.items():
            # Decode the base64-encoded certificate content
            cert_bytes = base64.b64decode(cert_content)

            logger.info("Deploying certificate %s to bucket %s", cert_name, bucket_name)

            # Upload the certificate to S3
            s3_client.put_object(
                Bucket=bucket_name,
                Key=cert_name,
                Body=cert_bytes,
                ContentType='application/x-x509-ca-cert'
            )

        logger.info("Successfully deployed %d certificates to %s", len(certificates), bucket_name)
        return True
    except Exception as e:
        logger.error("Error deploying certificates: %s", str(e))
        return False

def handle_s3_notification_config(event, context):
    """
    Handle S3 bucket notification configuration.

    Args:
        event (dict): CloudFormation custom resource event
        context (LambdaContext): Lambda execution context

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        bucket_name = event['ResourceProperties']['BucketName']
        notification_config = event['ResourceProperties'].get('NotificationConfiguration', {})

        if event['RequestType'] == 'Create':
            # For creation, just apply the notification configuration
            success = configure_bucket_notifications(bucket_name, notification_config)

        elif event['RequestType'] == 'Update':
            # For updates, apply the new notification configuration
            success = configure_bucket_notifications(bucket_name, notification_config)

        elif event['RequestType'] == 'Delete':
            # For deletion, disable notifications
            success = configure_bucket_notifications(bucket_name, {})

        else:
            logger.error("Unsupported request type: %s", event['RequestType'])
            return False

        return success
    except Exception as e:
        logger.error("Error handling S3 notification config: %s", str(e))
        return False

def lambda_handler(event, context):
    """
    Phase 2: Deploy Microchip verifier certificates to S3 bucket.

    This function is used as a CloudFormation custom resource to deploy
    Microchip verifier certificates to an S3 bucket during stack creation
    or update. Notifications are handled by separate Phase 1 and Phase 3 functions.

    Args:
        event (dict): CloudFormation custom resource event
        context (LambdaContext): Lambda execution context

    Returns:
        None: Sends response to CloudFormation via cfnresponse
    """
    logger.info("Phase 2 - Certificate Deployment: Received event: %s", json.dumps(event))

    try:
        # Extract parameters from the event for certificate deployment
        bucket_name = event['ResourceProperties']['BucketName']
        certificates = event['ResourceProperties']['Certificates']

        if event['RequestType'] == 'Create':
            # Phase 2: Deploy certificates (notifications already disabled in Phase 1)
            success = deploy_certificates(bucket_name, certificates)

            if success:
                cfnresponse.send(event, context, cfnresponse.SUCCESS, {
                    'Message': (f'Phase 2: Successfully deployed {len(certificates)} '
                              f'certificates to {bucket_name}')
                })
            else:
                cfnresponse.send(event, context, cfnresponse.FAILED, {
                    'Message': f'Phase 2: Failed to deploy certificates to {bucket_name}'
                })

        elif event['RequestType'] == 'Update':
            # Phase 2: Update certificates (notifications handled by separate phases)
            success = deploy_certificates(bucket_name, certificates)

            if success:
                cfnresponse.send(event, context, cfnresponse.SUCCESS, {
                    'Message': (f'Phase 2: Successfully updated {len(certificates)} '
                              f'certificates in {bucket_name}')
                })
            else:
                cfnresponse.send(event, context, cfnresponse.FAILED, {
                    'Message': f'Phase 2: Failed to update certificates in {bucket_name}'
                })

        elif event['RequestType'] == 'Delete':
            # No need to delete the certificates, as the bucket will be deleted by CloudFormation
            cfnresponse.send(event, context, cfnresponse.SUCCESS, {
                'Message': 'Phase 2: No action needed for Delete'
            })
        else:
            cfnresponse.send(event, context, cfnresponse.FAILED, {
                'Message': f'Unsupported request type: {event["RequestType"]}'
            })
    except Exception as e:
        logger.error("Phase 2 Error: %s", str(e))
        cfnresponse.send(event, context, cfnresponse.FAILED, {
            'Message': f'Phase 2 Error: {str(e)}'
        })

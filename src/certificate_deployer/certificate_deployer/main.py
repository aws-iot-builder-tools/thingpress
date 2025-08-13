# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""Lambda function to deploy Microchip verifier certificates to S3 bucket.
"""
import base64
import json

import boto3
from botocore.exceptions import ClientError
from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.utilities.data_classes import CloudFormationCustomResourceEvent

from . import cfnresponse

logger = Logger()

def deploy_certificates(bucket_name, certificates):
    """Deploy certificates to the S3 bucket.

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

def remove_certificates(bucket_name, certificate_keys):
    """Remove certificates from S3 bucket during stack deletion.

    Args:
        bucket_name (str): Name of the S3 bucket
        certificate_keys (list): List of certificate keys to remove (≤10)

    Returns:
        bool: True if successful, False otherwise
    """
    logger.info("Removing %d certificates from bucket %s", len(certificate_keys), bucket_name)
    s3_client = boto3.client('s3')

    # This routine does not fail when a certificate is not found. If the certificate is not
    # found, then it assumes the job is done. Also, if the bucket is not found 
    for cert_key in certificate_keys:
        try:
            if s3_client.delete_object(Bucket=bucket_name, Key=cert_key):
                logger.info("Removed certificate: %s", cert_key)
        except ClientError as e:
            if 'Error' in e.response:
                if 'Code' in e.response['Error']:
                    if e.response['Error']['Code'] == 'NoSuchKey':
                        # Ignore NoSuchKey - certificate already removed
                        logger.info("Certificate %s already removed or does not exist", cert_key)
                    if e.response['Error']['Code'] == 'NoSuchBucket':
                        # Ignore NoSuchBucket - whole bucket already removed
                        logger.info("Bucket %s already removed or does not exist", bucket_name)
                    else:
                        # Signals hard failure, some other boto error occurred
                        return False
            else:
                # This signals a hard failure
                logger.error("Failed to remove certificate %s: %s", cert_key, str(e))
                return False

    logger.info("Successfully removed certificates from %s", bucket_name)
    return True

def lambda_handler(event: dict, context: LambdaContext) -> None:
    """Deploy Microchip verifier certificates to S3 bucket or configure S3 notifications.

    This function is used as a CloudFormation custom resource to either:
    1. Deploy Microchip verifier certificates to an S3 bucket
    2. Configure S3 bucket notifications

    Args:
        event (dict): CloudFormation custom resource event
        context (LambdaContext): Lambda execution context
    """
    logger.info("Certificate Deployer: Received event: %s", json.dumps(event))
    custom_resource_event = CloudFormationCustomResourceEvent(event)

    try:
        # Handle certificate deployment
        bucket_name = event['ResourceProperties']['BucketName']
        certificates = event['ResourceProperties']['Certificates']

        if event['RequestType'] == 'Create':

            if success:= deploy_certificates(bucket_name, certificates):
                cfnresponse.send(custom_resource_event, context, cfnresponse.SUCCESS, {
                    'Message': (f'Successfully deployed {len(certificates)} '
                                f'certificates to {bucket_name}: {success}')
                })
            else:
                cfnresponse.send(custom_resource_event, context, cfnresponse.FAILED, {
                    'Message': f'Failed to deploy certificates to {bucket_name}'
                })

        elif event['RequestType'] == 'Update':

            if success:= deploy_certificates(bucket_name, certificates):
                cfnresponse.send(custom_resource_event, context, cfnresponse.SUCCESS, {
                    'Message': (f'Successfully updated {len(certificates)} '
                                f'certificates in {bucket_name}: {success}')
                })
            else:
                cfnresponse.send(custom_resource_event, context, cfnresponse.FAILED, {
                    'Message': f'Failed to update certificates in {bucket_name}'
                })

        elif event['RequestType'] == 'Delete':
            # Remove certificates before bucket deletion
            certificates = event['ResourceProperties']['Certificates']
            certificate_keys = list(certificates.keys())

            if success:= remove_certificates(bucket_name, certificate_keys):
                cfnresponse.send(custom_resource_event, context, cfnresponse.SUCCESS, {
                    'Message': f'Successfully removed {len(certificate_keys)} '
                               f'certificates from {bucket_name}: {success}'
                })
            else:
                cfnresponse.send(custom_resource_event, context, cfnresponse.FAILED, {
                    'Message': f'Failed to remove certificates from {bucket_name}'
                })
        else:
            cfnresponse.send(custom_resource_event, context, cfnresponse.FAILED, {
                'Message': f'Unsupported request type: {event["RequestType"]}'
            })
    except Exception as e:
        logger.error("Certificate Deployer Error: %s", str(e))
        cfnresponse.send(custom_resource_event, context, cfnresponse.FAILED, {
            'Message': f'Certificate Deployer Error: {str(e)}'
        })

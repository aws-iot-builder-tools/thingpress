"""
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

Lambda function to deploy Microchip verifier certificates to S3 bucket.
"""
import base64
import json

import boto3
from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.utilities.data_classes import CloudFormationCustomResourceEvent

from . import cfnresponse

logger = Logger()

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

def lambda_handler(event: dict, context: LambdaContext):
    """
    Deploy Microchip verifier certificates to S3 bucket or configure S3 notifications.

    This function is used as a CloudFormation custom resource to either:
    1. Deploy Microchip verifier certificates to an S3 bucket
    2. Configure S3 bucket notifications

    Args:
        event (dict): CloudFormation custom resource event
        context (LambdaContext): Lambda execution context

    Returns:
        None: Sends response to CloudFormation via cfnresponse
    """
    logger.info("Certificate Deployer: Received event: %s", json.dumps(event))
    custom_resource_event = CloudFormationCustomResourceEvent(event)

    try:
        # Handle certificate deployment
        bucket_name = event['ResourceProperties']['BucketName']
        certificates = event['ResourceProperties']['Certificates']

        if event['RequestType'] == 'Create':
            success = deploy_certificates(bucket_name, certificates)

            if success:
                cfnresponse.send(custom_resource_event, context, cfnresponse.SUCCESS, {
                    'Message': (f'Successfully deployed {len(certificates)} '
                              f'certificates to {bucket_name}')
                })
            else:
                cfnresponse.send(custom_resource_event, context, cfnresponse.FAILED, {
                    'Message': f'Failed to deploy certificates to {bucket_name}'
                })

        elif event['RequestType'] == 'Update':
            success = deploy_certificates(bucket_name, certificates)

            if success:
                cfnresponse.send(custom_resource_event, context, cfnresponse.SUCCESS, {
                    'Message': (f'Successfully updated {len(certificates)} '
                              f'certificates in {bucket_name}')
                })
            else:
                cfnresponse.send(custom_resource_event, context, cfnresponse.FAILED, {
                    'Message': f'Failed to update certificates in {bucket_name}'
                })

        elif event['RequestType'] == 'Delete':
            # No need to delete the certificates, as the bucket will be deleted by CloudFormation
            cfnresponse.send(custom_resource_event, context, cfnresponse.SUCCESS, {
                'Message': 'No action needed for Delete'
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

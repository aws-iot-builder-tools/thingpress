"""
Unified Thingpress cleanup functionality

This module provides comprehensive cleanup of Thingpress resources including:
- IoT Things, certificates, and policies
- S3 buckets and objects
- CloudFormation stacks
- Resource verification
"""

import logging
import time
#from typing import List, Dict, Any, Optional, Tuple
from typing import Dict, Any
import boto3
from botocore.exceptions import ClientError, NoCredentialsError

from .cleanup_config import CleanupConfig, ACTIVE_STACK_STATUSES


class ThingpressCleanup:
    """Unified cleanup class for Thingpress resources"""

    def __init__(self, config: CleanupConfig):
        """Initialize cleanup with configuration
        
        Args:
            config: CleanupConfig instance with cleanup parameters
        """
        self.config = config
        self.logger = logging.getLogger(__name__)

        # Initialize AWS clients
        session = boto3.Session(
            profile_name=config.profile_name,
            region_name=config.region
        )

        try:
            self.iot_client = session.client('iot')
            self.s3_client = session.client('s3')
            self.cf_client = session.client('cloudformation')
        except NoCredentialsError as e:
            self.logger.error("AWS credentials not found: %s", e)
            raise

        # Track cleanup results
        self.cleanup_results = {
            'iot_things_deleted': [],
            'iot_certificates_deleted': [],
            's3_buckets_cleaned': [],
            'cf_stacks_deleted': [],
            'errors': [],
            'dry_run': config.dry_run
        }

    def cleanup_all(self) -> Dict[str, Any]:
        """Perform complete cleanup of all Thingpress resources
        
        Returns:
            Dictionary with cleanup results and statistics
        """
        self.logger.info("🧹 Starting Thingpress cleanup (dry_run=%s)", self.config.dry_run)
        self.logger.info("Region: %s, Stack prefix: %s",
                         self.config.region, self.config.stack_name_prefix)

        try:
            # Step 1: Clean up IoT resources
            if self.config.cleanup_iot_resources:
                self._cleanup_iot_resources()

            # Step 2: Clean up S3 resources
            if self.config.cleanup_s3_resources:
                self._cleanup_s3_resources()

            # Step 3: Clean up CloudFormation stacks
            if self.config.cleanup_cloudformation_stacks:
                self._cleanup_cloudformation_stacks()

            # Step 4: Verify cleanup
            if self.config.verify_cleanup and not self.config.dry_run:
                self.logger.info("⏳ Waiting %ss for resources to fully delete...",
                                 self.config.verification_wait_seconds)
                time.sleep(self.config.verification_wait_seconds)
                verification_results = self._verify_cleanup()
                self.cleanup_results['verification'] = verification_results

            self.logger.info("🏁 Cleanup process completed!")
            return self.cleanup_results

        except Exception as e:
            self.logger.error("Cleanup failed: %s", e)
            self.cleanup_results['errors'].append(str(e))
            raise

    def cleanup_test_resources_only(self) -> Dict[str, Any]:
        """Clean up only test-specific resources (for integration tests)
        
        This is a lighter cleanup that only removes test IoT things and certificates,
        without touching S3 buckets or CloudFormation stacks.
        
        Returns:
            Dictionary with cleanup results
        """
        self.logger.info("🧹 Cleaning up test-specific Thingpress resources")

        # Only clean up IoT resources matching test patterns
        self._cleanup_test_iot_things()

        return self.cleanup_results

    def _cleanup_iot_resources(self):
        """Clean up IoT Things, certificates, and policies"""
        self.logger.info("🔧 Cleaning up IoT resources...")

        # Get all IoT things
        try:
            paginator = self.iot_client.get_paginator('list_things')

            for page in paginator.paginate():
                things = page.get('things', [])

                for thing in things:
                    thing_name = thing['thingName']
                    self._cleanup_single_iot_thing(thing_name)

        except ClientError as e:
            error_msg = f"Failed to list IoT things: {e}"
            self.logger.error(error_msg)
            self.cleanup_results['errors'].append(error_msg)

    def _cleanup_test_iot_things(self):
        """Clean up only IoT things matching test patterns"""
        self.logger.info("🔧 Cleaning up test IoT things...")

        try:
            paginator = self.iot_client.get_paginator('list_things')

            for page in paginator.paginate():
                things = page.get('things', [])

                for thing in things:
                    thing_name = thing['thingName']
                    self._cleanup_single_iot_thing(thing_name)

        except ClientError as e:
            error_msg = f"Failed to list test IoT things: {e}"
            self.logger.error(error_msg)
            self.cleanup_results['errors'].append(error_msg)

    def _cleanup_single_iot_thing(self, thing_name: str):
        """Clean up a single IoT thing and its associated resources"""
        try:
            self.logger.info("  📱 Cleaning up IoT thing: %s", thing_name)

            if self.config.dry_run:
                self.logger.info("    [DRY RUN] Would delete thing: %s", thing_name)
                return

            # Get attached certificates/principals
            try:
                principals_response = self.iot_client.list_thing_principals(thingName=thing_name)
                principals = principals_response.get('principals', [])

                # Detach and clean up each certificate
                for principal_arn in principals:
                    self._cleanup_certificate_from_thing(thing_name, principal_arn)

            except ClientError as e:
                self.logger.warning("    Failed to get principals for %s: %s", thing_name, e)

            # Delete the thing itself
            try:
                self.iot_client.delete_thing(thingName=thing_name)
                self.cleanup_results['iot_things_deleted'].append(thing_name)
                self.logger.info("    ✅ Deleted IoT thing: %s", thing_name)

            except ClientError as e:
                error_msg = f"Failed to delete thing {thing_name}: {e}"
                self.logger.error("    ❌ %s", error_msg)
                self.cleanup_results['errors'].append(error_msg)

        except ClientError as e:
            error_msg = f"Failed to cleanup thing {thing_name}: {e}"
            self.logger.error(error_msg)
            self.cleanup_results['errors'].append(error_msg)

    def _cleanup_certificate_from_thing(self, thing_name: str, principal_arn: str):
        """Clean up certificate associated with a thing"""
        try:
            # Extract certificate ID from ARN
            if 'cert/' not in principal_arn:
                return

            cert_id = principal_arn.split('/')[-1]

            # Detach policies from certificate
            try:
                policies_response = self.iot_client.list_principal_policies(principal=principal_arn)
                for policy in policies_response.get('policies', []):
                    policy_name = policy['policyName']
                    try:
                        self.iot_client.detach_policy(policyName=policy_name, target=principal_arn)
                        self.logger.info("    🔓 Detached policy %s from certificate %a",
                                         policy_name, cert_id)
                    except ClientError as e:
                        self.logger.warning("    Failed to detach policy %s: %s", policy_name, e)

            except ClientError as e:
                self.logger.warning("    Failed to list policies for certificate %s: %s",
                                    cert_id, e)

            # Detach certificate from thing
            try:
                self.iot_client.detach_thing_principal(thingName=thing_name,
                                                       principal=principal_arn)
                self.logger.info("    🔗 Detached certificate %s from thing %s",
                                 cert_id, thing_name)
            except ClientError as e:
                self.logger.warning("    Failed to detach certificate %s from thing: %s",
                                    cert_id, e)

            # Update certificate to INACTIVE and delete
            try:
                self.iot_client.update_certificate(certificateId=cert_id, newStatus='INACTIVE')
                self.iot_client.delete_certificate(certificateId=cert_id, forceDelete=True)
                self.cleanup_results['iot_certificates_deleted'].append(cert_id)
                self.logger.info("    🗑️ Deleted certificate: %s", cert_id)

            except ClientError as e:
                self.logger.warning("    Failed to delete certificate %s: %s", cert_id, e)

        except ClientError as e:
            self.logger.error("    Failed to cleanup certificate %s: %s", principal_arn, e)

    def _cleanup_s3_resources(self):
        """Clean up S3 buckets tagged with thingpress"""
        self.logger.info("🪣 Cleaning up S3 resources...")

        try:
            # List all buckets
            buckets_response = self.s3_client.list_buckets()
            buckets = buckets_response.get('Buckets', [])

            for bucket in buckets:
                bucket_name = bucket['Name']

                if self._should_cleanup_s3_bucket(bucket_name):
                    self._cleanup_single_s3_bucket(bucket_name)

        except ClientError as e:
            error_msg = f"Failed to list S3 buckets: {e}"
            self.logger.error(error_msg)
            self.cleanup_results['errors'].append(error_msg)

    def _should_cleanup_s3_bucket(self, bucket_name: str) -> bool:
        """Check if S3 bucket should be cleaned up"""
        try:
            # Check bucket tags
            tags_response = self.s3_client.get_bucket_tagging(Bucket=bucket_name)
            tags = {tag['Key']: tag['Value'] for tag in tags_response.get('TagSet', [])}

            return tags.get(self.config.resource_tag_key) == self.config.resource_tag_value

        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchTagSet':
                # No tags on bucket
                return False
            else:
                self.logger.warning("Failed to get tags for bucket %s: %s", bucket_name, e)
                return False

    def _cleanup_single_s3_bucket(self, bucket_name: str):
        """Clean up a single S3 bucket and its contents"""
        self.logger.info("  📦 Cleaning up S3 bucket: %s", bucket_name)

        if self.config.dry_run:
            self.logger.info("    [DRY RUN] Would empty and prepare bucket: %s", bucket_name)
            return

        try:
            # Empty bucket contents
            self._empty_s3_bucket(bucket_name)
            self.cleanup_results['s3_buckets_cleaned'].append(bucket_name)
            self.logger.info("    ✅ Emptied S3 bucket: %s", bucket_name)

        except ClientError as e:
            error_msg = f"Failed to clean S3 bucket {bucket_name}: {e}"
            self.logger.error("    ❌ %s", error_msg)
            self.cleanup_results['errors'].append(error_msg)

    def _empty_s3_bucket(self, bucket_name: str):
        """Empty all contents from an S3 bucket"""
        # Delete all objects
        paginator = self.s3_client.get_paginator('list_objects_v2')
        for page in paginator.paginate(Bucket=bucket_name):
            objects = page.get('Contents', [])
            if objects:
                delete_keys = [{'Key': obj['Key']} for obj in objects]
                self.s3_client.delete_objects(
                    Bucket=bucket_name,
                    Delete={'Objects': delete_keys}
                )

        # Delete all object versions if versioning is enabled
        try:
            paginator = self.s3_client.get_paginator('list_object_versions')
            for page in paginator.paginate(Bucket=bucket_name):
                versions = page.get('Versions', [])
                delete_markers = page.get('DeleteMarkers', [])

                objects_to_delete = []
                for version in versions:
                    objects_to_delete.append({
                        'Key': version['Key'],
                        'VersionId': version['VersionId']
                    })

                for marker in delete_markers:
                    objects_to_delete.append({
                        'Key': marker['Key'],
                        'VersionId': marker['VersionId']
                    })

                if objects_to_delete:
                    self.s3_client.delete_objects(
                        Bucket=bucket_name,
                        Delete={'Objects': objects_to_delete}
                    )
        except ClientError:
            # Versioning might not be enabled
            pass

        # Abort multipart uploads
        try:
            uploads_response = self.s3_client.list_multipart_uploads(Bucket=bucket_name)
            uploads = uploads_response.get('Uploads', [])

            for upload in uploads:
                self.s3_client.abort_multipart_upload(
                    Bucket=bucket_name,
                    Key=upload['Key'],
                    UploadId=upload['UploadId']
                )
        except ClientError:
            pass

    def _cleanup_cloudformation_stacks(self):
        """Clean up CloudFormation stacks with thingpress prefix"""
        self.logger.info("☁️ Cleaning up CloudFormation stacks...")

        try:
            # List stacks with prefix
            paginator = self.cf_client.get_paginator('list_stacks')

            for page in paginator.paginate(StackStatusFilter=ACTIVE_STACK_STATUSES):
                stacks = page.get('StackSummaries', [])

                for stack in stacks:
                    stack_name = stack['StackName']

                    if self._should_cleanup_stack(stack_name):
                        self._cleanup_single_stack(stack_name)

        except ClientError as e:
            error_msg = f"Failed to list CloudFormation stacks: {e}"
            self.logger.error(error_msg)
            self.cleanup_results['errors'].append(error_msg)

    def _should_cleanup_stack(self, stack_name: str) -> bool:
        """Check if CloudFormation stack should be cleaned up"""
        # Check prefix
        if not stack_name.startswith(self.config.stack_name_prefix):
            return False

        # Check stack tags
        try:
            stacks_response = self.cf_client.describe_stacks(StackName=stack_name)
            stacks = stacks_response.get('Stacks', [])

            if stacks:
                tags = {tag['Key']: tag['Value'] for tag in stacks[0].get('Tags', [])}
                return tags.get(self.config.resource_tag_key) == self.config.resource_tag_value

        except ClientError:
            # If we can't check tags, rely on prefix matching
            pass

        return True  # Default to cleanup if prefix matches

    def _cleanup_single_stack(self, stack_name: str):
        """Clean up a single CloudFormation stack"""
        self.logger.info("  🗂️ Cleaning up CloudFormation stack: %s", stack_name)

        if self.config.dry_run:
            self.logger.info("    [DRY RUN] Would delete stack: %s", stack_name)
            return

        try:
            self.cf_client.delete_stack(StackName=stack_name)

            # Wait for deletion to complete
            waiter = self.cf_client.get_waiter('stack_delete_complete')
            waiter.wait(
                StackName=stack_name,
                WaiterConfig={
                    'Delay': 30,
                    'MaxAttempts': self.config.stack_deletion_timeout_minutes * 2
                }
            )

            self.cleanup_results['cf_stacks_deleted'].append(stack_name)
            self.logger.info("    ✅ Deleted CloudFormation stack: %s", stack_name)

        except ClientError as e:
            error_msg = f"Failed to delete stack {stack_name}: {e}"
            self.logger.error("    ❌ %s", error_msg)
            self.cleanup_results['errors'].append(error_msg)
    
    def _verify_cleanup(self) -> Dict[str, Any]:
        """Verify that cleanup was successful"""
        self.logger.info("✅ Verifying cleanup completion...")
        
        verification_results = {
            'success': True,
            'remaining_resources': {
                'iot_things': [],
                's3_buckets': [],
                'cf_stacks': []
            },
            'issues_found': 0
        }
        
        # Check for remaining IoT things
        try:
            paginator = self.iot_client.get_paginator('list_things')
            for page in paginator.paginate():
                things = page.get('things', [])
                for thing in things:
                    if self._should_cleanup_thing(thing['thingName'], thing):
                        verification_results['remaining_resources']['iot_things'].append(thing['thingName'])
                        verification_results['issues_found'] += 1
        except ClientError as e:
            self.logger.warning("Failed to verify IoT things cleanup: %s", e)

        # Check for remaining S3 buckets
        try:
            buckets_response = self.s3_client.list_buckets()
            for bucket in buckets_response.get('Buckets', []):
                if self._should_cleanup_s3_bucket(bucket['Name']):
                    verification_results['remaining_resources']['s3_buckets'].append(bucket['Name'])
                    verification_results['issues_found'] += 1
        except ClientError as e:
            self.logger.warning("Failed to verify S3 buckets cleanup: %s", e)

        # Check for remaining CloudFormation stacks
        if self.config.cleanup_cloudformation_stacks:
            try:
                paginator = self.cf_client.get_paginator('list_stacks')
                for page in paginator.paginate(StackStatusFilter=ACTIVE_STACK_STATUSES):
                    for stack in page.get('StackSummaries', []):
                        if self._should_cleanup_stack(stack['StackName']):
                            verification_results['remaining_resources']['cf_stacks'].append(stack['StackName'])
                            verification_results['issues_found'] += 1
            except ClientError as e:
                self.logger.warning("Failed to verify CloudFormation stacks cleanup: %s", e)

        # Log results
        if verification_results['issues_found'] == 0:
            self.logger.info(
                "  🎉 Cleanup verification PASSED - All resources cleaned up successfully!")
            verification_results['success'] = True
        else:
            self.logger.error("  ❌ Cleanup verification FAILED - %s issues found",
                              verification_results['issues_found'])
            verification_results['success'] = False

            # Log remaining resources
            for resource_type, resources in verification_results['remaining_resources'].items():
                if resources:
                    self.logger.error("    Remaining %s: %s", resource_type, resources)

        return verification_results

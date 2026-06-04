"""
End-to-End Black-Box Test Framework for Thingpress

Tests the complete deployed Thingpress system by:
1. Uploading manifests to S3 ingest buckets
2. Monitoring processing through CloudWatch logs and SQS queues
3. Verifying IoT things are created with proper configuration
4. Validating certificate deployer integration
5. Checking end-to-end workflow completion
"""

import os
import sys
import time
import logging
import traceback
from datetime import datetime
from pathlib import Path
import boto3
from botocore.exceptions import ClientError
from integration.cleanup_utils import ThingpressCleanup, CleanupConfig

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

class EndToEndTestFramework:
    """Framework for end-to-end black-box testing of Thingpress"""

    def __init__(self, test_name: str, region: str = 'us-east-1'):
        self.test_name = test_name
        self.region = region
        self.test_id = f"{test_name}-{int(time.time())}"
        self.logger = logging.getLogger(f"e2e.{test_name}")

        # AWS clients
        self.s3_client = boto3.client('s3', region_name=region)
        self.iot_client = boto3.client('iot', region_name=region)
        self.cloudformation = boto3.client('cloudformation', region_name=region)
        self.logs_client = boto3.client('logs', region_name=region)
        self.sqs_client = boto3.client('sqs', region_name=region)

        # Test resources to cleanup
        self.cleanup_resources = []

        # Test results
        self.results = {
            'test_name': test_name,
            'test_id': self.test_id,
            'start_time': datetime.now().isoformat(),
            'steps': [],
            'success': False,
            'error': None,
            'iot_things_created': [],
            'certificates_processed': 0
        }

        # Get deployed resources
        self.resources = self._get_deployed_resources()

    def is_thing_creation_deferred(self) -> bool:
        """Check if thing creation is deferred based on stack parameters"""
        return self.stack_params.get('IoTThingDeferred', 'FALSE') == 'TRUE'

    def log_step(self, step_name: str, description: str = ""):
        """Log a test step"""
        step = {
            'name': step_name,
            'description': description,
            'start_time': datetime.now().isoformat(),
            'success': False,
            'duration_ms': 0,
            'details': {}
        }
        self.results['steps'].append(step)
        self.logger.info("🔄 Starting step: %s - %s", step_name, description)
        return step

    def complete_step(self, step: dict, success: bool = True, details: dict | None = None):
        """Complete a test step"""
        end_time = datetime.now()
        start_time = datetime.fromisoformat(step['start_time'])
        duration_ms = (end_time - start_time).total_seconds() * 1000

        step['success'] = success
        step['duration_ms'] = duration_ms
        step['end_time'] = end_time.isoformat()
        if details:
            step['details'].update(details)

        status = "✅" if success else "❌"
        self.logger.info("%s Completed step: %s (%d:.2fms)",
                         status, step['name'], duration_ms)

    def _get_deployed_resources(self) -> dict[str, str]:
        """Get deployed Thingpress resources from CloudFormation stack"""
        try:
            # Allow stack name to be configured via environment variable
            stack_name = os.environ.get('THINGPRESS_STACK_NAME', 'sam-app')
            response = self.cloudformation.describe_stacks(StackName=stack_name)
            stack = response['Stacks'][0]
            
            outputs = stack['Outputs']
            resources = {}
            for output in outputs:
                key = output['OutputKey']
                value = output['OutputValue']
                resources[key] = value

            # Get stack parameters for conditional validation
            parameters = stack.get('Parameters', [])
            self.stack_params = {}
            for param in parameters:
                self.stack_params[param['ParameterKey']] = param['ParameterValue']

            self.logger.info("Found %d deployed resources", len(resources))
            self.logger.info("Stack parameters: %s", self.stack_params)
            return resources

        except Exception as e:
            self.logger.error("Failed to get deployed resources: %s", e)
            raise

    def upload_manifest(self, provider: str, manifest_path: str) -> str:
        """Upload a manifest file to the provider's S3 ingest bucket"""

        # Get the ingest bucket for the provider
        bucket_key = f"{provider.title()}IngestPoint"
        if bucket_key not in self.resources:
            raise ValueError(f"Ingest bucket not found for {provider}")

        bucket = self.resources[bucket_key]

        # Create unique key for this test
        file_extension = Path(manifest_path).suffix
        manifest_key = f"e2e-test/{self.test_id}/manifest{file_extension}"

        # Upload the file
        with open(manifest_path, 'rb') as f:
            self.s3_client.upload_fileobj(f, bucket, manifest_key)

        # Add to cleanup
        self.cleanup_resources.append(('s3', bucket, manifest_key))

        self.logger.info("Uploaded manifest to s3://%s/%s",
                         bucket, manifest_key)
        return f"s3://{bucket}/{manifest_key}"

    def wait_for_processing_completion(self, timeout_minutes: int = 10, manifest_cert_count: int = 1000) -> dict:
        """Wait for Thingpress processing to complete by monitoring various indicators"""

        start_time = time.time()
        timeout_seconds = timeout_minutes * 60

        processing_indicators = {
            'recent_iot_things': [],
            'log_activity': False,
            'queue_activity': False,
            'certificates_found': 0
        }

        thing_deferred = self.is_thing_creation_deferred()
        if thing_deferred:
            self.logger.info("⚠️  Thing creation is DEFERRED - will not validate thing creation")
        
        self.logger.info("Monitoring processing for up to %d minutes...", timeout_minutes)

        # Give the system a moment to start processing after manifest upload
        time.sleep(5)

        while (time.time() - start_time < timeout_seconds):

            # Check for recently created IoT things (use longer window for detection)
            things = [] if thing_deferred else self._get_iot_things(manifest_cert_count)
            certificates = self._get_iot_certificates(manifest_cert_count)
            things_completed = thing_deferred  # If deferred, skip thing check
            certificates_completed = False
            
            if things:
                processing_indicators['iot_things'] = things
                self.logger.info("Found %d recent IoT things", len(things))
                things_completed = len(things) == manifest_cert_count 
            if certificates:
                processing_indicators['iot_certificates'] = certificates
                self.logger.info("Found %d recent IoT certificates", len(certificates))
                certificates_completed = len(certificates) == manifest_cert_count

            if things_completed and certificates_completed:
                self.logger.info("🎉 All certificates discovered%s!", 
                               " (things deferred)" if thing_deferred else " and things created")
                break

            # Check for log activity in provider functions
            log_activity = self._check_recent_log_activity()
            if log_activity:
                processing_indicators['log_activity'] = True
                self.logger.info("Detected recent log activity in provider functions")

            # Wait before next check
            time.sleep(10)

        total_wait_time = time.time() - start_time
        self.logger.info("Monitoring completed after %d:.1fs", total_wait_time)

        return processing_indicators

    def _get_iot_things(self, max_expected: int=1000) -> list[dict]:
        """Get IoT things created"""
        things = []
        try:
            # Get all things (this might need pagination for large deployments)
            response = self.iot_client.list_things(maxResults=max_expected)
        except ClientError as e:
            self.logger.error("Failed to get recent IoT things: %s", e)
            return []

        for thing in response.get('things', []):
            # Get additional details about the thing
            # TODO: This is ok for now but inefficient, we should get details only
            #       when the test completes
            thing_details = self._get_thing_details(thing['thingName'])
            things.append(thing_details)

        return things

    def _get_iot_certificates(self, max_expected: int=1000) -> list[dict]:
        """Get IoT certificates created"""
        certificates = []
        try:
            # Get all things (this might need pagination for large deployments)
            response = self.iot_client.list_certificates(pageSize=max_expected)
        except ClientError as e:
            self.logger.error("Failed to get recent IoT things: %s", e)
            return []

        for certificate in response.get('certificates', []):
            # Get additional details about the thing
            # TODO: This is ok for now but inefficient, we should get details only
            #       when the test completes
            certificate_details = {"certificate": certificate['certificateId']}
            certificates.append(certificate_details)

        return certificates


    def _get_thing_details(self, thing_name: str) -> dict:
        """Get detailed information about an IoT thing"""
        try:
            # Get thing description
            thing_response = self.iot_client.describe_thing(thingName=thing_name)

            # Get attached certificates (principals)
            principals_response = self.iot_client.list_thing_principals(thingName=thing_name)
            certificates = principals_response.get('principals', [])

            # Get policies attached to each certificate
            # NOTE: Policies attach to CERTIFICATES, not things
            policies = []
            for cert_arn in certificates:
                try:
                    policy_response = self.iot_client.list_principal_policies(principal=cert_arn)
                    cert_policies = [p['policyName'] for p in policy_response.get('policies', [])]
                    policies.extend(cert_policies)
                except:
                    pass  # Best effort

            # Get thing groups (things are members of groups)
            thing_groups = []
            try:
                groups_response = self.iot_client.list_thing_groups_for_thing(thingName=thing_name)
                thing_groups = [g['groupName'] for g in groups_response.get('thingGroups', [])]
            except Exception as e:
                self.logger.warning(f"Failed to get thing groups for {thing_name}: {e}")

            return {
                'thingName': thing_name,
                'thingType': thing_response.get('thingTypeName'),  # Thing type applied to thing
                'thingGroups': thing_groups,  # Thing membership in groups
                'attributes': thing_response.get('attributes', {}),
                'certificates': certificates,  # Certificates attached to thing
                'policies': list(set(policies)),  # Policies attached to certificates (deduplicated)
                'creationDate': thing_response.get('creationDate').isoformat() if thing_response.get('creationDate') else None
            }

        except Exception as e:
            self.logger.error(f"Failed to get details for thing {thing_name}: {e}")
            return {'thingName': thing_name, 'error': str(e)}

    def _check_recent_log_activity(self) -> bool:
        """Check for recent log activity in Thingpress Lambda functions"""
        try:
            # Check logs for provider functions
            provider_functions = [
                self.resources.get('MicrochipProviderFunction'),
                self.resources.get('EspressifProviderFunction'),
                self.resources.get('InfineonProviderFunction'),
                self.resources.get('GeneratedProviderFunction'),
                self.resources.get('BulkImporterFunction')
            ]

            recent_activity = False
            cutoff_time = int((time.time() - 300) * 1000)  # Last 5 minutes

            for function_name in provider_functions:
                if not function_name:
                    continue

                log_group = f"/aws/lambda/{function_name}"

                try:
                    # Get recent log streams
                    streams_response = self.logs_client.describe_log_streams(
                        logGroupName=log_group,
                        orderBy='LastEventTime',
                        descending=True,
                        limit=5
                    )

                    for stream in streams_response.get('logStreams', []):
                        if stream.get('lastEventTime', 0) > cutoff_time:
                            recent_activity = True
                            break

                    if recent_activity:
                        break

                except Exception as e:
                    self.logger.debug("Could not check logs for %s: %s",
                                      function_name, e)

            return recent_activity

        except Exception as e:
            self.logger.error("Failed to check log activity: %s",e )
            return False

    def verify_certificate_deployer_integration(self) -> dict:
        """Verify that certificate deployer has created verification certificates"""
        try:
            # Check the Microchip verification certificates bucket
            verification_bucket = self.resources.get('MicrochipVerificationCertsBucket')
            if not verification_bucket:
                return {'verified': False, 'error': 'Verification bucket not found'}

            # List objects in verification bucket
            response = self.s3_client.list_objects_v2(Bucket=verification_bucket)
            objects = response.get('Contents', [])

            # Accept both .cer and .crt file extensions for verification certificates
            verification_certs = [obj['Key'] for obj in objects if obj['Key'].endswith(('.cer', '.crt'))]

            return {
                'verified': len(verification_certs) > 0,
                'verification_bucket': verification_bucket,
                'verification_certificates': verification_certs,
                'total_objects': len(objects)
            }

        except Exception as e:
            self.logger.error("Failed to verify certificate deployer: %s", e)
            return {'verified': False, 'error': str(e)}

    def cleanup_existing_test_data(self):
        """Clean up existing test data before running test using unified cleanup module"""
        self.logger.info("🧹 Cleaning up existing test data before test run")

        try:
            # Create configuration for integration test cleanup
            cleanup_config = CleanupConfig.for_integration_tests(
                stack_name=os.getenv('THINGPRESS_STACK_NAME', 'thingpress'),
                region=self.region
            )

            # Initialize cleanup with our existing AWS clients
            cleanup = ThingpressCleanup(cleanup_config)

            # Override the clients to use our existing ones (to maintain session consistency)
            cleanup.iot_client = self.iot_client
            cleanup.s3_client = self.s3_client

            # Perform test-specific cleanup (only IoT resources, no stacks)
            cleanup_results = cleanup.cleanup_test_resources_only()

            # Log results
            things_deleted = cleanup_results.get('iot_things_deleted', [])
            certs_deleted = cleanup_results.get('iot_certificates_deleted', [])
            errors = cleanup_results.get('errors', [])

            if things_deleted:
                self.logger.info(f"Deleted {len(things_deleted)} IoT things: {things_deleted[:3]}{'...' if len(things_deleted) > 3 else ''}")

            if certs_deleted:
                self.logger.info(f"Deleted {len(certs_deleted)} certificates: {certs_deleted[:3]}{'...' if len(certs_deleted) > 3 else ''}")

            if errors:
                self.logger.warning(f"Cleanup encountered {len(errors)} errors: {errors[:2]}{'...' if len(errors) > 2 else ''}")

        except ImportError as e:
            self.logger.warning(f"Could not import unified cleanup module, falling back to legacy cleanup: {e}")
            self._legacy_cleanup_existing_test_data()
        except Exception as e:
            self.logger.warning(f"Unified cleanup failed, falling back to legacy cleanup: {e}")
            self._legacy_cleanup_existing_test_data()

    def _legacy_cleanup_existing_test_data(self):
        """Legacy cleanup method as fallback"""
        self.logger.info("Using legacy cleanup method")

        try:
            # Clean up IoT things that match test patterns
            response = self.iot_client.list_things(maxResults=100)
            test_thing_names = []

            for thing in response.get('things', []):
                thing_name = thing['thingName']
                # Look for things that match test certificate patterns
                if any(pattern in thing_name for pattern in ['0123ff', 'test_', 'microchip_e2e']):
                    test_thing_names.append(thing_name)

            # Clean up each test thing
            for thing_name in test_thing_names:
                try:
                    # First, detach and delete certificates
                    principals_response = self.iot_client.list_thing_principals(thingName=thing_name)
                    for principal_arn in principals_response.get('principals', []):
                        if 'cert/' in principal_arn:
                            cert_id = principal_arn.split('/')[-1]
                            try:
                                # Detach certificate from thing
                                self.iot_client.detach_thing_principal(
                                    thingName=thing_name,
                                    principal=principal_arn
                                )

                                # Update certificate to INACTIVE before deletion
                                self.iot_client.update_certificate(
                                    certificateId=cert_id,
                                    newStatus='INACTIVE'
                                )

                                # Delete certificate
                                self.iot_client.delete_certificate(
                                    certificateId=cert_id,
                                    forceDelete=True
                                )
                                self.logger.info("Deleted certificate %s", cert_id)

                            except Exception as cert_e:
                                self.logger.warning("Failed to delete certificate %s: %s",
                                                    cert_id, cert_e)

                    # Delete the thing
                    self.iot_client.delete_thing(thingName=thing_name)
                    self.logger.info("Deleted IoT thing %s", thing_name)

                except Exception as thing_e:
                    self.logger.warning("Failed to delete thing %s: %s", thing_name, thing_e)

        except Exception as e:
            self.logger.warning("Legacy cleanup failed: %s", e)

    def cleanup_test_resources(self):
        """Clean up test resources"""
        self.logger.info("🧹 Starting test resource cleanup")

        for resource_type, *args in self.cleanup_resources:
            try:
                if resource_type == 's3':
                    bucket, key = args
                    self.s3_client.delete_object(Bucket=bucket, Key=key)
                    self.logger.info("Deleted s3://%s/%s", bucket, key)
                elif resource_type == 'iot_thing':
                    thing_name = args[0]
                    # Note: In a real cleanup, we'd also detach policies and certificates
                    # For now, we'll leave test IoT things for inspection
                    self.logger.info("IoT thing %s left for inspection", thing_name)

            except Exception as e:
                self.logger.warning("Failed to cleanup %s %s: %s", resource_type, args, e)

    def finalize_test(self, success: bool = True, error: str | None = None):
        """Finalize test results"""
        self.results['end_time'] = datetime.now().isoformat()
        self.results['success'] = success
        if error:
            self.results['error'] = error

        # Calculate total duration
        start_time = datetime.fromisoformat(self.results['start_time'])
        end_time = datetime.fromisoformat(self.results['end_time'])
        total_duration = (end_time - start_time).total_seconds() * 1000
        self.results['total_duration_ms'] = total_duration

        # Add validation summary if validation was performed
        self._add_validation_summary()

        # Cleanup resources
        self.cleanup_test_resources()

        # Log final result with validation details
        status = "🎉 PASSED" if success else "❌ FAILED"
        self.logger.info("%s Test %s completed in %.2fms",
                         status, self.test_name, total_duration)

        if error:
            self.logger.error("Error: %s", error)
        
        # Log validation summary
        self._log_validation_summary()

        return self.results

    def _add_validation_summary(self):
        """Add detailed validation summary to test results"""
        # Find validation step
        validation_step = None
        for step in self.results.get('steps', []):
            if step['name'] == 'validate_iot_config':
                validation_step = step
                break
        
        if not validation_step or 'details' not in validation_step:
            return
        
        validation_details = validation_step['details']
        
        # Create high-level summary
        self.results['validation_summary'] = {
            'total_things': validation_details.get('total_things', 0),
            'things_validated': validation_details.get('things_validated', 0),
            'success_rate': validation_details.get('success_rate', 0.0),
            'policies': {
                'expected': list(self.expected_config.get('policies', [])),
                'expected_count': len(self.expected_config.get('policies', [])),
                'exact_match_count': validation_details.get('summary', {}).get('correct_policies', 0),
                'count_mismatch_count': validation_details.get('summary', {}).get('policy_count_mismatches', 0)
            },
            'thing_groups': {
                'expected': list(self.expected_config.get('thing_groups', [])),
                'expected_count': len(self.expected_config.get('thing_groups', [])),
                'exact_match_count': validation_details.get('summary', {}).get('correct_thing_groups', 0),
                'count_mismatch_count': validation_details.get('summary', {}).get('thing_group_count_mismatches', 0)
            },
            'thing_type': {
                'expected': self.expected_config.get('thing_type'),
                'correct_count': validation_details.get('summary', {}).get('correct_thing_types', 0),
                'incorrect_count': len(validation_details.get('summary', {}).get('incorrect_thing_types', []))
            }
        }
    
    def _log_validation_summary(self):
        """Log validation summary to console"""
        if 'validation_summary' not in self.results:
            return
        
        summary = self.results['validation_summary']
        
        self.logger.info("=" * 60)
        self.logger.info("VALIDATION SUMMARY")
        self.logger.info("=" * 60)
        self.logger.info(f"Total Things: {summary['total_things']}")
        self.logger.info(f"Things Validated: {summary['things_validated']}")
        self.logger.info(f"Success Rate: {summary['success_rate']:.1%}")
        self.logger.info("")
        
        # Policies
        policies = summary['policies']
        self.logger.info(f"Policies (Expected: {policies['expected_count']})")
        self.logger.info(f"  Expected: {policies['expected']}")
        self.logger.info(f"  Exact Matches: {policies['exact_match_count']}/{summary['total_things']}")
        if policies['count_mismatch_count'] > 0:
            self.logger.warning(f"  ⚠️  Count Mismatches: {policies['count_mismatch_count']}")
        
        # Thing Groups
        groups = summary['thing_groups']
        self.logger.info(f"Thing Groups (Expected: {groups['expected_count']})")
        self.logger.info(f"  Expected: {groups['expected']}")
        self.logger.info(f"  Exact Matches: {groups['exact_match_count']}/{summary['total_things']}")
        if groups['count_mismatch_count'] > 0:
            self.logger.warning(f"  ⚠️  Count Mismatches: {groups['count_mismatch_count']}")
        
        # Thing Type (singular)
        thing_type = summary['thing_type']
        self.logger.info(f"Thing Type (Expected: {thing_type['expected']})")
        self.logger.info(f"  Correct: {thing_type['correct_count']}/{summary['total_things']}")
        if thing_type['incorrect_count'] > 0:
            self.logger.warning(f"  ⚠️  Incorrect: {thing_type['incorrect_count']}")
        
        self.logger.info("=" * 60)


class ProviderEndToEndTest(EndToEndTestFramework):
    """Base class for provider-specific end-to-end tests"""

    def __init__(self, provider_name: str, manifest_path: str,
                 manifest_cert_count: int, region: str = 'us-east-1'):
        super().__init__(f"{provider_name}_e2e", region)
        self.provider_name = provider_name
        self.manifest_path = Path(manifest_path)
        self.manifest_cert_count = manifest_cert_count

        if not self.manifest_path.exists():
            raise FileNotFoundError(f"Test manifest not found: {manifest_path}")
        
        # Get expected configuration from deployed stack (DATA-DRIVEN)
        self.expected_config = self._get_expected_config_from_stack()

    def _get_expected_config_from_stack(self) -> dict:
        """Retrieve expected configuration from CloudFormation stack parameters
        
        This is DATA-DRIVEN - reads actual deployment parameters, not hardcoded values.
        Different workflows/stacks can have different configurations.
        """
        try:
            stack_name = os.environ.get('THINGPRESS_STACK_NAME', 'sam-app')
            response = self.cloudformation.describe_stacks(StackName=stack_name)
            parameters = response['Stacks'][0]['Parameters']
            
            # Build expected config from stack parameters
            expected_config = {
                'policies': [],
                'thing_groups': [],
                'thing_type': None  # Singular - AWS IoT allows only one thing type per thing
            }
            
            # Extract configuration from stack parameters
            for param in parameters:
                param_key = param['ParameterKey']
                param_value = param['ParameterValue']
                
                # Handle multi-value parameters (comma-delimited)
                if param_key == 'IoTPolicies' and param_value and param_value != 'None':
                    expected_config['policies'] = [
                        p.strip() for p in param_value.split(',') 
                        if p.strip() and p.strip() != 'None'
                    ]
                
                # Handle thing groups
                elif param_key == 'IoTThingGroups' and param_value and param_value != 'None':
                    expected_config['thing_groups'] = [
                        g.strip() for g in param_value.split(',')
                        if g.strip() and g.strip() != 'None'
                    ]
                
                # Handle thing type (singular - AWS IoT allows only one thing type per thing)
                elif param_key == 'IoTThingType' and param_value and param_value != 'None':
                    expected_config['thing_type'] = param_value
            
            self.logger.info(f"Expected config from stack: {expected_config}")
            return expected_config
            
        except Exception as e:
            self.logger.error(f"Failed to get expected config from stack: {e}")
            # Return empty config rather than failing
            return {'policies': [], 'thing_groups': [], 'thing_type': None}

    def run_test(self, timeout_minutes: int = 10) -> dict:
        """Run the complete end-to-end test for this provider"""

        try:
            # Step 0: Clean up existing test data for fresh test environment
            self.cleanup_existing_test_data()

            # Step 1: Upload manifest
            step1 = self.log_step("upload_manifest", f"Upload {self.provider_name} manifest to S3")
            manifest_s3_path = self.upload_manifest(self.provider_name, str(self.manifest_path))
            self.complete_step(step1, True, {'manifest_path': manifest_s3_path})

            # Step 2: Wait for processing
            step2 = self.log_step("wait_processing",
                                  f"Wait for {self.provider_name} processing to complete")
            processing_results = self.wait_for_processing_completion(timeout_minutes, self.manifest_cert_count)

            iot_certificates = processing_results.get('iot_certificates', [])
            iot_things = processing_results.get('iot_things', [])

            if len(iot_certificates) > 0:
                self.results['certificates_processed'] = len(iot_certificates)
                self.results['iot_things_created'] = [thing['thingName'] for thing in iot_things]

            self.complete_step(step2, len(iot_certificates) > 0, {
                'certificates_processed': len(iot_certificates),
                'iot_things_created': len(iot_things),
                'processing_indicators': processing_results
            })

            # Step 3: Verify certificate deployer (for Microchip)
            if self.provider_name.lower() == 'microchip':
                step3 = self.log_step("verify_cert_deployer",
                                      "Verify certificate deployer integration")
                cert_deployer_results = self.verify_certificate_deployer_integration()
                self.complete_step(step3, cert_deployer_results.get('verified', False),
                                   cert_deployer_results)

            # Step 4: Validate IoT thing configuration
            step4 = self.log_step("validate_iot_config", "Validate IoT thing configuration")
            validation_results = self._validate_iot_things(iot_things)
            self.complete_step(step4, validation_results.get('valid', False), validation_results)

            # Determine overall success
            overall_success = (
                len(iot_certificates) > 0 and
                validation_results.get('valid', False)
            )

            self.finalize_test(success=overall_success)
            return self.results

        except Exception as e:
            self.logger.error("Test failed: %s",e)
            self.logger.error(traceback.format_exc())
            self.finalize_test(success=False, error=str(e))
            return self.results

    def _validate_iot_things(self, iot_things: list[dict]) -> dict:
        """Validate that IoT things EXACTLY match expected configuration
        
        Validates:
        - Policies attached to certificates (exact match)
        - Thing membership in thing groups (exact match)
        - Thing type applied to thing (exact match)
        """
        if not iot_things:
            return {'valid': False, 'error': 'No IoT things to validate'}

        expected_policies = set(self.expected_config.get('policies', []))
        expected_groups = set(self.expected_config.get('thing_groups', []))
        expected_type = self.expected_config.get('thing_type')  # Singular

        validation_results = {
            'valid': True,
            'total_things': len(iot_things),
            'things_validated': 0,
            'validation_details': [],
            'summary': {
                'correct_policies': 0,
                'correct_thing_groups': 0,
                'correct_thing_types': 0,
                'policy_count_mismatches': 0,
                'thing_group_count_mismatches': 0,
                'missing_policies': [],
                'missing_thing_groups': [],
                'extra_policies': [],
                'extra_thing_groups': [],
                'incorrect_thing_types': []
            }
        }

        for thing in iot_things:
            # Policies are attached to certificates (not directly to things)
            thing_policies = set(thing.get('policies', []))
            
            # Things are members of thing groups
            thing_groups = set(thing.get('thingGroups', []))
            
            # Thing type is applied to thing
            thing_type = thing.get('thingType')

            # EXACT MATCH: Check policies attached to certificates
            policies_exact_match = thing_policies == expected_policies
            missing_policies = expected_policies - thing_policies
            extra_policies = thing_policies - expected_policies
            policy_count_match = len(thing_policies) == len(expected_policies)

            # EXACT MATCH: Check thing group membership
            groups_exact_match = thing_groups == expected_groups
            missing_groups = expected_groups - thing_groups
            extra_groups = thing_groups - expected_groups
            group_count_match = len(thing_groups) == len(expected_groups)

            # EXACT MATCH: Check thing type applied to thing (singular)
            type_match = thing_type == expected_type if expected_type else (thing_type is None)

            thing_validation = {
                'thing_name': thing['thingName'],
                'policies': {
                    'expected': list(expected_policies),
                    'expected_count': len(expected_policies),
                    'actual': list(thing_policies),
                    'actual_count': len(thing_policies),
                    'exact_match': policies_exact_match,
                    'count_match': policy_count_match,
                    'missing': list(missing_policies),
                    'extra': list(extra_policies)
                },
                'thing_groups': {
                    'expected': list(expected_groups),
                    'expected_count': len(expected_groups),
                    'actual': list(thing_groups),
                    'actual_count': len(thing_groups),
                    'exact_match': groups_exact_match,
                    'count_match': group_count_match,
                    'missing': list(missing_groups),
                    'extra': list(extra_groups)
                },
                'thing_type': {
                    'expected': expected_type,
                    'actual': thing_type,
                    'match': type_match
                },
                'overall_valid': policies_exact_match and groups_exact_match and type_match
            }

            if thing_validation['overall_valid']:
                validation_results['things_validated'] += 1

            if policies_exact_match:
                validation_results['summary']['correct_policies'] += 1
            else:
                if not policy_count_match:
                    validation_results['summary']['policy_count_mismatches'] += 1
                validation_results['summary']['missing_policies'].extend(missing_policies)
                validation_results['summary']['extra_policies'].extend(extra_policies)

            if groups_exact_match:
                validation_results['summary']['correct_thing_groups'] += 1
            else:
                if not group_count_match:
                    validation_results['summary']['thing_group_count_mismatches'] += 1
                validation_results['summary']['missing_thing_groups'].extend(missing_groups)
                validation_results['summary']['extra_thing_groups'].extend(extra_groups)

            if type_match:
                validation_results['summary']['correct_thing_types'] += 1
            else:
                validation_results['summary']['incorrect_thing_types'].append(thing_type)

            validation_results['validation_details'].append(thing_validation)

        # Overall validation passes ONLY if ALL things have EXACT configuration match
        validation_results['valid'] = (
            validation_results['things_validated'] == validation_results['total_things']
        )

        validation_results['success_rate'] = (
            validation_results['things_validated'] / validation_results['total_things']
        )
        
        # Add certificate tracking for test reporting
        things_with_certs = sum(1 for thing in iot_things if thing.get('certificates'))
        validation_results['things_with_certificates'] = things_with_certs
        validation_results['certificate_success_rate'] = validation_results['success_rate']

        return validation_results

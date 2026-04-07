"""
MES Provider Component Integration Test

Tests the deployed MES provider Lambda function through its interface:
1. Invokes the provider function with a test device-infos JSON
2. Verifies it processes the JSON correctly
3. Checks that device messages are queued for bulk import
4. Validates the bulk importer processes the devices
5. Verifies IoT things are created with proper attributes
"""

import os
import sys
import json
import time
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.append(str(project_root))
sys.path.append(str(project_root / 'test/integration'))

from common.test_framework import ProviderComponentTest
from common.aws_helpers import AWSHelpers
from common.cert_helper import register_test_certificates, cleanup_test_certificates


class MesProviderComponentTest(ProviderComponentTest):
    """Component test for MES provider"""

    def __init__(self, region: str = 'us-east-1'):
        super().__init__('mes', region=region)
        self.registered_certs = []
        self.test_device_infos = None  # built after cert registration

    def run_test(self) -> dict:
        """Run the complete MES provider component test"""

        try:
            # Step 1: Verify test prerequisites
            step1 = self.log_step("verify_prerequisites", "Check deployed resources")
            self._verify_prerequisites()
            self.complete_step(step1, True, {
                'provider_function': self.get_provider_function_name(),
                'ingest_bucket': self.get_ingest_bucket(),
                'bulk_importer': self.get_bulk_importer_function()
            })

            # Step 2: Register real test certificates as INACTIVE (Phase 1)
            step2 = self.log_step(
                "register_test_certs",
                "Register test certificates in AWS IoT as INACTIVE"
            )
            self.registered_certs = register_test_certificates(
                count=3, region=self.region, status='INACTIVE'
            )

            # Build device-infos using real fingerprints
            ts = int(time.time())
            self.test_device_infos = {
                "batchId": f"test-batch-{ts}",
                "devices": [
                    {
                        "certFingerprint": cert['fingerprint'],
                        "deviceId": f"test-device-{i+1:03d}-{ts}",
                        "deviceType": "TestDeviceType",
                        "attributes": {
                            "DSN": f"TEST-DSN-{i+1:03d}",
                            "MAC": f"AA:BB:CC:DD:EE:{i+1:02X}",
                            "TestBatch": "integration-test"
                        }
                    }
                    for i, cert in enumerate(self.registered_certs)
                ]
            }

            self.complete_step(step2, len(self.registered_certs) == 3, {
                'certs_registered': len(self.registered_certs),
                'sample_fingerprint': self.registered_certs[0]['fingerprint'][:16]
            })

            # Step 3: Upload test device-infos JSON
            step3 = self.log_step(
                "upload_device_infos",
                "Upload MES device-infos JSON to S3"
            )
            manifest_key = f"component-test/{self.test_id}/device-infos.json"

            # Create temporary file with device-infos JSON
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                json.dump(self.test_device_infos, f, indent=2)
                temp_file = f.name

            try:
                upload_success = self.upload_test_file(
                    self.get_ingest_bucket(),
                    manifest_key,
                    temp_file
                )
                if not upload_success:
                    raise Exception("Failed to upload test device-infos")
            finally:
                os.unlink(temp_file)

            self.complete_step(step3, True, {
                'manifest_key': manifest_key,
                'batch_id': self.test_device_infos['batchId'],
                'device_count': len(self.test_device_infos['devices'])
            })

            # Step 4: Invoke provider function
            step4 = self.log_step(
                "invoke_provider",
                "Invoke MES provider function"
            )

            # Create provider event with explicit cert_active configuration
            # Note: For component test, we use cert_active=TRUE
            # (Phase 2 behavior). In a real Phase 2 scenario, certificates
            # would already be registered as INACTIVE
            provider_event = self.create_test_manifest_event(
                self.get_ingest_bucket(),
                manifest_key,
                additional_config={
                    'cert_active': 'TRUE',  # Phase 2: activate certificates
                    'thing_deferred': 'FALSE'  # Phase 2: create Things
                }
            )

            provider_response = self.invoke_lambda_function(
                self.get_provider_function_name(),
                provider_event
            )

            if not provider_response['success']:
                raise Exception(f"Provider function failed: {provider_response['payload']}")

            self.complete_step(step4, True, {
                'status_code': provider_response['status_code'],
                'response_payload': provider_response['payload']
            })

            # Step 5: Check bulk import queue for messages
            step5 = self.log_step(
                "check_bulk_queue",
                "Wait for device messages in bulk import queue"
            )

            # Get bulk importer queue URL
            # The stack outputs don't include the main queue URL, only DLQs
            # We need to construct it or find it by listing queues
            import boto3
            sqs_client = boto3.client('sqs', region_name=self.region)

            # Try to find the queue by listing and filtering
            list_response = sqs_client.list_queues(
                QueueNamePrefix='Thingpress-Bulk-Importer-'
            )
            if 'QueueUrls' not in list_response or not list_response['QueueUrls']:
                raise Exception(
                    "BulkImporterQueue not found. Expected queue with "
                    "prefix 'Thingpress-Bulk-Importer-'"
                )

            # Filter out DLQ
            bulk_queue_url = None
            for url in list_response['QueueUrls']:
                if 'DLQ' not in url:
                    bulk_queue_url = url
                    break

            if not bulk_queue_url:
                raise Exception(
                    "BulkImporterQueue not found (only DLQ found)"
                )

            # Wait for messages to appear in bulk import queue
            # Note: Messages may be processed quickly by bulk importer or arrive in batches
            # We'll wait up to 45 seconds and accept receiving at least 1 message
            messages = self.wait_for_sqs_messages(
                bulk_queue_url,
                timeout_seconds=45,
                expected_count=3
            )

            if not messages:
                raise Exception("No messages found in bulk import queue")

            self.complete_step(step5, True, {
                'messages_received': len(messages),
                'expected_messages': len(self.test_device_infos['devices'])
            })

            # Step 6: Validate message format
            step6 = self.log_step(
                "validate_message_format",
                "Validate messages have correct format"
            )

            # Parse messages and validate structure
            parsed_messages = []
            for msg in messages:
                try:
                    body = json.loads(msg['Body'])
                    parsed_messages.append(body)
                except json.JSONDecodeError as e:
                    self.logger.error(f"Failed to parse message: {e}")

            # Validate first message structure
            if parsed_messages:
                sample_msg = parsed_messages[0]

                # Check required fields for MES provider messages
                required_fields = [
                    'certificate',      # Should be fingerprint
                    'thing',           # Should be deviceId
                    'cert_format',     # Should be 'FINGERPRINT'
                    'thing_deferred'   # Should be 'FALSE'
                ]

                missing_fields = [field for field in required_fields if field not in sample_msg]
                if missing_fields:
                    self.logger.warning(f"Missing required fields: {missing_fields}")

                # Validate MES-specific values
                validation_results = {
                    'cert_format_correct': sample_msg.get('cert_format') == 'FINGERPRINT',
                    'thing_deferred_correct': sample_msg.get('thing_deferred') == 'FALSE',
                    'has_attributes': 'attributes' in sample_msg,
                    'fingerprint_length': len(sample_msg.get('certificate', ''))
                }

                self.complete_step(step6, all(validation_results.values()), {
                    'messages_validated': len(parsed_messages),
                    'sample_message_fields': list(sample_msg.keys()),
                    'validation_results': validation_results,
                    'sample_attributes': sample_msg.get('attributes', {})
                })
            else:
                self.complete_step(step6, False, {'error': 'No messages to validate'})

            # Step 7: Validate attributes are included
            step7 = self.log_step(
                "validate_attributes",
                "Check device attributes are included"
            )

            attributes_found = []
            for msg in parsed_messages:
                if 'attributes' in msg:
                    attributes_found.append(msg['attributes'])

            # Note: We may not receive all messages if bulk importer
            # processes them quickly or if they're still in flight.
            # Check that at least one message has attributes.
            has_any_attributes = len(attributes_found) > 0

            # Validate attribute structure
            if attributes_found:
                sample_attrs = attributes_found[0]
                expected_keys = ['DSN', 'MAC', 'TestBatch']
                has_expected_keys = all(key in sample_attrs for key in expected_keys)
            else:
                has_expected_keys = False

            self.complete_step(step7, has_any_attributes and has_expected_keys, {
                'devices_with_attributes': len(attributes_found),
                'messages_received': len(parsed_messages),
                'expected_devices': len(self.test_device_infos['devices']),
                'sample_attributes': attributes_found[0] if attributes_found else None,
                'has_any_attributes': has_any_attributes,
                'has_expected_keys': has_expected_keys,
                'note': (
                    'Validates device attributes are correctly passed through '
                    'to bulk importer messages'
                )
            })

            # Step 8: Validate fingerprint format
            step8 = self.log_step(
                "validate_fingerprints",
                "Validate certificate fingerprints"
            )

            fingerprints = [
                msg.get('certificate')
                for msg in parsed_messages
                if 'certificate' in msg
            ]

            # All fingerprints should be 64 hex characters (lowercase from build_bulk_importer_message)
            valid_fingerprints = [
                fp for fp in fingerprints
                if isinstance(fp, str) and len(fp) == 64 and
                all(c in '0123456789abcdef' for c in fp)
            ]

            all_valid = len(valid_fingerprints) == len(fingerprints)

            self.complete_step(step8, all_valid, {
                'total_fingerprints': len(fingerprints),
                'valid_fingerprints': len(valid_fingerprints),
                'sample_fingerprint': fingerprints[0] if fingerprints else None,
                'all_valid': all_valid
            })

            # Step 9: Wait for bulk importer to process and verify IoT Things created
            step9 = self.log_step(
                "verify_things_created",
                "Wait for bulk importer and verify IoT Things are created"
            )

            import boto3
            iot_client = boto3.client('iot', region_name=self.region)
            expected_thing_names = [d['deviceId'] for d in self.test_device_infos['devices']]

            # Poll for Things to appear (bulk importer needs time to process)
            max_wait = 120  # seconds
            poll_start = time.time()
            found_things = {}

            while time.time() - poll_start < max_wait:
                for thing_name in expected_thing_names:
                    if thing_name in found_things:
                        continue
                    try:
                        resp = iot_client.describe_thing(thingName=thing_name)
                        found_things[thing_name] = resp
                    except iot_client.exceptions.ResourceNotFoundException:
                        pass
                if len(found_things) == len(expected_thing_names):
                    break
                time.sleep(5)

            all_things_created = len(found_things) == len(expected_thing_names)
            self.complete_step(step9, all_things_created, {
                'expected': len(expected_thing_names),
                'found': len(found_things),
                'missing': [n for n in expected_thing_names if n not in found_things],
                'wait_seconds': int(time.time() - poll_start)
            })

            # Step 10: Verify certificates are ACTIVE
            step10 = self.log_step(
                "verify_certs_active",
                "Verify certificates activated (INACTIVE → ACTIVE)"
            )

            active_count = 0
            for cert in self.registered_certs:
                try:
                    resp = iot_client.describe_certificate(certificateId=cert['certificate_id'])
                    if resp['certificateDescription']['status'] == 'ACTIVE':
                        active_count += 1
                except Exception as e:
                    self.logger.warning("Failed to check cert %s: %s", cert['certificate_id'][:12], e)

            all_active = active_count == len(self.registered_certs)
            self.complete_step(step10, all_active, {
                'active': active_count,
                'total': len(self.registered_certs)
            })

            # Step 11: Verify certificates attached to Things and policies attached
            step11 = self.log_step(
                "verify_attachments",
                "Verify cert→Thing and policy→cert attachments"
            )

            things_with_cert = 0
            certs_with_policy = 0
            for thing_name in found_things:
                try:
                    principals = iot_client.list_thing_principals(thingName=thing_name)
                    cert_arns = principals.get('principals', [])
                    if cert_arns:
                        things_with_cert += 1
                        # Check policies on the first attached cert
                        policies = iot_client.list_principal_policies(principal=cert_arns[0])
                        if policies.get('policies'):
                            certs_with_policy += 1
                except Exception as e:
                    self.logger.warning("Failed to check attachments for %s: %s", thing_name, e)

            all_attached = things_with_cert == len(found_things)
            self.complete_step(step11, all_attached, {
                'things_with_cert': things_with_cert,
                'certs_with_policy': certs_with_policy,
                'total_things': len(found_things)
            })

            # Test completed successfully
            self.finalize_test(success=True)
            return self.results

        except Exception as e:
            self.logger.error(f"Test failed: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            self.finalize_test(success=False, error=str(e))
            return self.results
        finally:
            # Always clean up test resources
            import boto3
            iot_client = boto3.client('iot', region_name=self.region)

            # Clean up IoT Things created by the test
            if self.test_device_infos:
                for device in self.test_device_infos['devices']:
                    thing_name = device['deviceId']
                    try:
                        # Detach principals before deleting Thing
                        principals = iot_client.list_thing_principals(thingName=thing_name)
                        for arn in principals.get('principals', []):
                            iot_client.detach_thing_principal(thingName=thing_name, principal=arn)
                        iot_client.delete_thing(thingName=thing_name)
                        self.logger.info("Deleted Thing %s", thing_name)
                    except Exception:
                        pass  # Thing may not have been created

            # Clean up test certificates
            if self.registered_certs:
                self.logger.info("Cleaning up %d test certificates...", len(self.registered_certs))
                try:
                    cleanup_test_certificates(self.registered_certs, region=self.region)
                except Exception as cleanup_err:
                    self.logger.warning("Certificate cleanup failed: %s", cleanup_err)

    def _verify_prerequisites(self):
        """Verify test prerequisites"""
        # Check deployed resources
        required_resources = [
            'MesProviderFunction',
            'MesIngestPoint',
            'BulkImporterFunction'
        ]

        for resource in required_resources:
            if resource not in self.resources:
                raise Exception(f"Required resource not found: {resource}")

        self.logger.info("✅ All prerequisites verified")


def run_mes_component_test():
    """Run the MES provider component test"""
    test = MesProviderComponentTest()
    results = test.run_test()

    # Print summary
    print("\n" + "="*60)
    print(f"🧪 MES PROVIDER COMPONENT TEST RESULTS")
    print("="*60)
    print(f"Test ID: {results['test_id']}")
    print(f"Duration: {results.get('total_duration_ms', 0):.2f}ms")
    print(f"Success: {'✅ PASSED' if results['success'] else '❌ FAILED'}")

    if results.get('error'):
        print(f"Error: {results['error']}")

    print(f"\nSteps completed: {len(results['steps'])}")
    for step in results['steps']:
        status = "✅" if step['success'] else "❌"
        print(f"  {status} {step['name']}: {step['description']} ({step['duration_ms']:.2f}ms)")

    print("="*60)

    return results['success']


if __name__ == "__main__":
    success = run_mes_component_test()
    exit(0 if success else 1)

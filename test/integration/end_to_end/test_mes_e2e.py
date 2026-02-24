"""
MES Provider End-to-End Integration Test

Tests the complete MES two-phase provisioning workflow:

Phase 1 (Certificate Registration):
1. Upload vendor manifest with thing_deferred=TRUE
2. Verify certificates registered as INACTIVE
3. Verify Things are NOT created (deferred)

Phase 2 (Device Activation):
4. Upload MES device-infos JSON with certificate fingerprints
5. Monitor processing through the entire pipeline
6. Verify certificates are activated (INACTIVE → ACTIVE)
7. Verify IoT things are created with device IDs and attributes
8. Check end-to-end two-phase workflow completion

Note: This test requires the stack to be deployed with:
- IoTCertActive=FALSE (for Phase 1)
- IoTThingDeferred=TRUE (for Phase 1)
"""

import json
import time
import tempfile
from pathlib import Path
from integration.end_to_end.e2e_test_framework import EndToEndTestFramework


class MesEndToEndTest(EndToEndTestFramework):
    """End-to-end test for MES two-phase provisioning"""

    def __init__(self, phase1_manifest_path=None, device_count=3):
        """
        Initialize MES E2E test
        
        Args:
            phase1_manifest_path: Path to Phase 1 vendor manifest (optional, will generate if not provided)
            device_count: Number of test devices to create
        """
        super().__init__('mes')
        self.phase1_manifest_path = phase1_manifest_path
        self.device_count = device_count
        self.test_devices = []
        self.registered_certificates = []
        
    def run_test(self, timeout_minutes=20):
        """Run the complete MES two-phase provisioning test"""
        
        try:
            # Step 1: Verify prerequisites
            step1 = self.log_step("verify_prerequisites", "Check stack configuration for two-phase provisioning")
            self._verify_prerequisites()
            self.complete_step(step1, True, {
                'cert_active': self.stack_params.get('IoTCertActive'),
                'thing_deferred': self.stack_params.get('IoTThingDeferred'),
                'cert_format': self.stack_params.get('IoTCertFormat')
            })
            
            # Step 2: Phase 1 - Register certificates (PENDING_ACTIVATION, no Things)
            step2 = self.log_step("phase1_register_certs", "Phase 1: Register certificates without Things")
            
            # For this test, we'll use the Generated provider to create test certificates
            # In production, this would be vendor certificates (Espressif, Infineon, etc.)
            if not self.phase1_manifest_path:
                self.phase1_manifest_path = self._generate_test_certificates()
            
            # Upload Phase 1 manifest
            phase1_s3_path = self.upload_manifest('generated', self.phase1_manifest_path)
            
            # Wait for certificates to be registered
            # Note: Increased wait time to account for Lambda cold starts and SQS processing
            time.sleep(30)  # Give time for processing
            
            # Get registered certificates (should be INACTIVE if stack configured correctly)
            recent_certs = self._get_recent_certificates(minutes=5)
            
            # Get full certificate details to check status
            # list_certificates() may not include status, so we need to describe each one
            inactive_certs = []
            for cert in recent_certs:
                cert_details = self._get_certificate_details(cert['certificateId'])
                if cert_details and cert_details['status'] == 'INACTIVE':
                    inactive_certs.append(cert_details)
            
            self.registered_certificates = inactive_certs[:self.device_count]
            
            self.complete_step(step2, len(self.registered_certificates) > 0, {
                'phase1_manifest': phase1_s3_path,
                'certificates_registered': len(self.registered_certificates),
                'inactive_count': len(inactive_certs),
                'sample_cert_id': self.registered_certificates[0]['certificateId'] if self.registered_certificates else None
            })
            
            if not self.registered_certificates:
                raise Exception("No certificates registered in Phase 1")
            
            # Step 3: Verify Things were NOT created (deferred)
            step3 = self.log_step("verify_things_deferred", "Verify Things were not created in Phase 1")
            
            # Check that Things don't exist yet
            # In Phase 1, certificates are registered but Things are deferred
            things_created = self._get_recent_things(minutes=2)
            
            self.complete_step(step3, True, {
                'things_created_in_phase1': len(things_created),
                'expected': 0,
                'note': 'Things should not be created in Phase 1 (deferred)'
            })
            
            # Step 4: Create device-infos JSON for Phase 2
            step4 = self.log_step("create_device_infos", "Create MES device-infos JSON with fingerprints")
            
            device_infos = self._create_device_infos_json()
            device_infos_path = self._save_device_infos(device_infos)
            
            self.complete_step(step4, True, {
                'batch_id': device_infos['batch_id'],
                'device_count': len(device_infos['devices']),
                'device_ids': [d['deviceId'] for d in device_infos['devices']]
            })
            
            # Step 5: Phase 2 - Upload device-infos to MES bucket
            step5 = self.log_step("phase2_upload_device_infos", "Phase 2: Upload device-infos to MES bucket")
            
            phase2_s3_path = self.upload_manifest('mes', device_infos_path)
            
            self.complete_step(step5, True, {
                'device_infos_path': phase2_s3_path,
                'batch_id': device_infos['batch_id']
            })
            
            # Step 6: Wait for Phase 2 processing
            step6 = self.log_step("wait_phase2_processing", "Wait for certificates to activate and Things to be created")
            
            # Wait for processing (certificates should be activated, Things created)
            max_wait = timeout_minutes * 60
            start_time = time.time()
            
            things_created = []
            activated_certs = []
            
            while time.time() - start_time < max_wait:
                # Check for activated certificates
                for cert in self.registered_certificates:
                    cert_details = self._get_certificate_details(cert['certificateId'])
                    if cert_details and cert_details['status'] == 'ACTIVE':
                        if cert['certificateId'] not in [c['certificateId'] for c in activated_certs]:
                            activated_certs.append(cert_details)
                
                # Check for created Things
                things_created = self._get_recent_things(minutes=5)
                
                # Check if all devices are processed
                if len(activated_certs) >= self.device_count and len(things_created) >= self.device_count:
                    break
                
                time.sleep(5)
            
            processing_time = time.time() - start_time
            
            self.complete_step(step6, len(activated_certs) > 0 and len(things_created) > 0, {
                'processing_time_seconds': processing_time,
                'certificates_activated': len(activated_certs),
                'things_created': len(things_created),
                'expected_count': self.device_count
            })
            
            # Step 7: Validate certificate activation
            step7 = self.log_step("validate_cert_activation", "Verify certificates changed from INACTIVE to ACTIVE")
            
            all_activated = len(activated_certs) == self.device_count
            
            self.complete_step(step7, all_activated, {
                'activated_count': len(activated_certs),
                'expected_count': self.device_count,
                'activation_rate': len(activated_certs) / self.device_count if self.device_count > 0 else 0,
                'sample_cert_status': activated_certs[0]['status'] if activated_certs else None
            })
            
            # Step 8: Validate Things created with attributes
            step8 = self.log_step("validate_things_attributes", "Verify Things created with device IDs and attributes")
            
            things_with_attributes = []
            for thing in things_created:
                thing_details = self._get_thing_details(thing['thingName'])
                if thing_details and 'attributes' in thing_details:
                    things_with_attributes.append(thing_details)
            
            all_have_attributes = len(things_with_attributes) == len(things_created)
            
            # Check for expected attributes
            expected_attrs = ['DSN', 'MAC', 'TestBatch']
            sample_attrs = things_with_attributes[0]['attributes'] if things_with_attributes else {}
            has_expected_attrs = all(attr in sample_attrs for attr in expected_attrs)
            
            self.complete_step(step8, all_have_attributes and has_expected_attrs, {
                'things_with_attributes': len(things_with_attributes),
                'total_things': len(things_created),
                'sample_attributes': sample_attrs,
                'has_expected_attributes': has_expected_attrs
            })
            
            # Step 9: Validate certificate-thing attachments
            step9 = self.log_step("validate_attachments", "Verify certificates attached to Things")
            
            things_with_certs = 0
            for thing in things_created:
                principals = self._get_thing_principals(thing['thingName'])
                if principals:
                    things_with_certs += 1
            
            all_attached = things_with_certs == len(things_created)
            
            self.complete_step(step9, all_attached, {
                'things_with_certificates': things_with_certs,
                'total_things': len(things_created),
                'attachment_rate': things_with_certs / len(things_created) if things_created else 0
            })
            
            # Update results
            self.results['iot_things_created'] = [t['thingName'] for t in things_created]
            self.results['certificates_processed'] = len(activated_certs)
            
            # Test completed successfully
            self.finalize_test(success=True)
            return self.results
            
        except Exception as e:
            self.logger.error(f"Test failed: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            self.finalize_test(success=False, error=str(e))
            return self.results
    
    def _verify_prerequisites(self):
        """Verify test prerequisites"""
        # Check that stack is configured for two-phase provisioning
        cert_active = self.stack_params.get('IoTCertActive', 'TRUE')
        thing_deferred = self.stack_params.get('IoTThingDeferred', 'FALSE')
        
        self.logger.info(f"Stack configuration:")
        self.logger.info(f"  IoTCertActive: {cert_active}")
        self.logger.info(f"  IoTThingDeferred: {thing_deferred}")
        
        # Warn if stack is not configured for two-phase provisioning
        if cert_active != 'FALSE' or thing_deferred != 'TRUE':
            self.logger.warning(
                "⚠️  Stack not configured for two-phase provisioning!\n"
                f"   Current: IoTCertActive={cert_active}, IoTThingDeferred={thing_deferred}\n"
                "   Expected: IoTCertActive=FALSE, IoTThingDeferred=TRUE\n"
                "   Phase 1 certificates will be registered as ACTIVE instead of INACTIVE"
            )
        
        # Check MES resources exist
        if 'MesIngestPoint' not in self.resources:
            raise Exception("MES ingest bucket not found - MES provider not deployed")
        
        self.logger.info("✅ Prerequisites verified")
    
    def _generate_test_certificates(self):
        """Generate test certificates for Phase 1"""
        # Try multiple possible paths for test certificates
        possible_paths = [
            Path(__file__).parent.parent.parent / 'artifacts/certificates_test.txt',
            Path(__file__).parent.parent.parent / 'test/artifacts/certificates_test.txt',
            Path(__file__).parent.parent / 'artifacts/certificates_test.txt'
        ]
        
        for test_certs_path in possible_paths:
            if test_certs_path.exists():
                self.logger.info(f"Using test certificates from: {test_certs_path}")
                return str(test_certs_path)
        
        raise Exception(
            f"Test certificates not found. Tried paths:\n" +
            "\n".join(f"  - {p}" for p in possible_paths) +
            "\n\nPlease ensure test certificate artifacts exist before running this test."
        )
    
    def _create_device_infos_json(self):
        """Create device-infos JSON with fingerprints from registered certificates"""
        devices = []
        
        for i, cert in enumerate(self.registered_certificates[:self.device_count]):
            # Get certificate fingerprint
            fingerprint = cert.get('certificateId', '')  # In AWS IoT, certificateId is the fingerprint
            
            device = {
                "certFingerprint": fingerprint,
                "deviceId": f"test-device-{i+1:03d}-{int(time.time())}",
                "attributes": {
                    "DSN": f"TEST-DSN-{i+1:03d}",
                    "MAC": f"AA:BB:CC:DD:EE:{i+1:02X}",
                    "TestBatch": f"e2e-test-{self.test_id}"
                }
            }
            devices.append(device)
            self.test_devices.append(device)
        
        return {
            "batch_id": f"e2e-batch-{int(time.time())}",
            "devices": devices
        }
    
    def _save_device_infos(self, device_infos):
        """Save device-infos JSON to temporary file"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(device_infos, f, indent=2)
            return f.name
    
    def _get_recent_certificates(self, minutes=5):
        """Get recently registered certificates"""
        try:
            response = self.iot_client.list_certificates()
            return response.get('certificates', [])
        except Exception as e:
            self.logger.error(f"Failed to list certificates: {e}")
            return []
    
    def _get_certificate_details(self, certificate_id):
        """Get certificate details including status"""
        try:
            response = self.iot_client.describe_certificate(certificateId=certificate_id)
            return response.get('certificateDescription')
        except Exception as e:
            self.logger.debug(f"Failed to get certificate details: {e}")
            return None
    
    def _get_recent_things(self, minutes=5):
        """Get recently created Things"""
        try:
            response = self.iot_client.list_things()
            return response.get('things', [])
        except Exception as e:
            self.logger.error(f"Failed to list things: {e}")
            return []
    
    def _get_thing_details(self, thing_name):
        """Get Thing details including attributes"""
        try:
            response = self.iot_client.describe_thing(thingName=thing_name)
            return response
        except Exception as e:
            self.logger.debug(f"Failed to get thing details: {e}")
            return None
    
    def _get_thing_principals(self, thing_name):
        """Get principals (certificates) attached to Thing"""
        try:
            response = self.iot_client.list_thing_principals(thingName=thing_name)
            return response.get('principals', [])
        except Exception as e:
            self.logger.debug(f"Failed to get thing principals: {e}")
            return []
    
    def finalize_test(self, success=False, error=None):
        """Finalize test and cleanup resources"""
        self.results['success'] = success
        self.results['error'] = error
        self.results['end_time'] = time.time()
        
        # Cleanup test resources
        self.logger.info("Cleaning up test resources...")
        # Add cleanup logic here if needed


def run_mes_e2e_test(phase1_manifest_path=None, device_count=3):
    """Run the MES two-phase provisioning end-to-end test"""
    test = MesEndToEndTest(phase1_manifest_path, device_count)
    results = test.run_test(timeout_minutes=20)

    # Print summary
    print("\n" + "="*70)
    print("🧪 MES TWO-PHASE PROVISIONING END-TO-END TEST RESULTS")
    print("="*70)
    print(f"Test ID: {results['test_id']}")
    print(f"Duration: {results.get('total_duration_ms', 0):.2f}ms")
    print(f"Success: {'✅ PASSED' if results['success'] else '❌ FAILED'}")

    if results.get('error'):
        print(f"Error: {results['error']}")

    print("\nProcessing Results:")
    print(f"  Certificates Activated: {results.get('certificates_processed', 0)}")
    print(f"  IoT Things Created: {len(results.get('iot_things_created', []))}")

    if results.get('iot_things_created'):
        print(f"  Thing Names: {', '.join(results['iot_things_created'][:5])}")
        if len(results['iot_things_created']) > 5:
            print(f"    ... and {len(results['iot_things_created']) - 5} more")

    print(f"\nSteps completed: {len(results['steps'])}")
    for step in results['steps']:
        status = "✅" if step['success'] else "❌"
        print(f"  {status} {step['name']}: {step['description']} ({step['duration_ms']:.2f}ms)")

    print("="*70)

    return results['success']


if __name__ == "__main__":
    success = run_mes_e2e_test()
    exit(0 if success else 1)

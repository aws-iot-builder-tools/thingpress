"""
Espressif Provider End-to-End Integration Test

Tests the complete Espressif provider workflow:
1. Upload CSV manifest to Espressif S3 ingest bucket
2. Monitor processing through the entire pipeline
3. Verify IoT things are created with proper configuration
4. Check end-to-end workflow completion
"""

from integration.end_to_end.e2e_test_framework import ProviderEndToEndTest

class EspressifEndToEndTest(ProviderEndToEndTest):
    """End-to-end test for Espressif provider"""
    def __init__(self, manifest_path, manifest_cert_count):
        super().__init__('espressif', manifest_path, manifest_cert_count)

def run_espressif_e2e_test(manifest_path, manifest_cert_count):
    """Run the Espressif provider end-to-end test"""
    test = EspressifEndToEndTest(manifest_path, manifest_cert_count)
    results = test.run_test(timeout_minutes=15)

    # Print summary
    print("\n" + "="*70)
    print("🧪 ESPRESSIF PROVIDER END-TO-END TEST RESULTS")
    print("="*70)
    print(f"Test ID: {results['test_id']}")
    print(f"Duration: {results.get('total_duration_ms', 0):.2f}ms")
    print(f"Success: {'✅ PASSED' if results['success'] else '❌ FAILED'}")

    if results.get('error'):
        print(f"Error: {results['error']}")

    print("\nProcessing Results:")
    print(f"  Certificates Processed: {results.get('certificates_processed', 0)}")
    print(f"  IoT Things Created: {len(results.get('iot_things_created', []))}")

    if results.get('iot_things_created'):
        print(f"  Thing Names: {', '.join(results['iot_things_created'][:5])}")
        if len(results['iot_things_created']) > 5:
            print(f"    ... and {len(results['iot_things_created']) - 5} more")

    print(f"\nSteps completed: {len(results['steps'])}")
    for step in results['steps']:
        status = "✅" if step['success'] else "❌"
        print(f"  {status} {step['name']}: {step['description']} ({step['duration_ms']:.2f}ms)")

        # Show key details for important steps
        if step['name'] == 'wait_processing' and step.get('details'):
            details = step['details']
            print(f"      Certificates: {details.get('certificates_processed', 0)}")
            print(f"      IoT Things: {details.get('iot_things_created', 0)}")

        elif step['name'] == 'validate_iot_config' and step.get('details'):
            details = step['details']
            print(f"      Success Rate: {details.get('certificate_success_rate', 0):.1%}")
            print(f"      Things with Certs: {details.get('things_with_certificates', 0)}")

    print("="*70)

    return results['success']


#if __name__ == "__main__":
#    success = run_espressif_e2e_test()
#    exit(0 if success else 1)

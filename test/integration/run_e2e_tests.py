#!/usr/bin/env python3
"""
End-to-End Integration Test Runner

Runs comprehensive end-to-end tests for all Thingpress providers.
Tests the complete deployed system as a black box by uploading manifests
and verifying the entire processing pipeline works correctly.
"""

import sys
import json
import time
import argparse
import hashlib
from datetime import datetime
from typing import List, Dict
import yaml
from pathlib import Path

# Import test modules
from integration.end_to_end.test_microchip_e2e import run_microchip_e2e_test
from integration.end_to_end.test_espressif_e2e import run_espressif_e2e_test
from integration.end_to_end.test_infineon_e2e import run_infineon_e2e_test
from integration.end_to_end.test_generated_e2e import run_generated_e2e_test

KEY_PROVIDERS = 'providers'
KEY_PROVIDER = 'provider'
KEY_BSHA256 = 'bSHA256'
KEY_FILE = 'file'
KEY_COUNT = 'count'

def calculate_file_sha256(file_path):
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            sha256_hash.update(chunk)
    return sha256_hash.hexdigest()

def verify_sha256(file_path, expected_hash):
    actual_hash = calculate_file_sha256(file_path)
    return actual_hash == expected_hash

class EndToEndTestRunner:
    """Runs and manages end-to-end integration tests"""

    def __init__(self):
        self.test_results = {}
        self.start_time = datetime.now()
        self.project_root = Path(__file__).parent.parent.parent

    def run_all_tests(self, providers: List[str] | None = None) -> Dict:
        """Run end-to-end tests for specified providers"""

        # Default to all providers if none specified
        if providers is None:
            providers = ['microchip', 'espressif', 'infineon', 'generated']

        print("🚀 Starting End-to-End Integration Test Suite")
        print("=" * 80)
        print("Testing Thingpress system as deployed black box")
        print(f"Providers to test: {', '.join(providers)}")
        print(f"Start time: {self.start_time.isoformat()}")
        print("=" * 80)

        # Test functions mapping
        test_functions = {
            'microchip': run_microchip_e2e_test,
            'espressif': run_espressif_e2e_test,
            'infineon': run_infineon_e2e_test,
            'generated': run_generated_e2e_test
        }

        # Run tests for each provider
        for provider in providers:
            if provider not in test_functions:
                print(f"❌ Unknown provider: {provider}")
                self.test_results[provider] = {
                    'success': False,
                    'error': f'Unknown provider: {provider}',
                    'duration_ms': 0
                }
                continue

            print(f"\n🧪 Testing {provider.upper()} Provider End-to-End...")
            print("-" * 50)

            artifacts_config= f"{self.project_root}/test/artifacts/test_artifacts.yml"
            with open(artifacts_config, 'r', encoding='UTF-8') as file:
                data = yaml.safe_load(file)
                if not KEY_PROVIDERS in data:
                    print("This is not a provider config file")
                    raise ValueError("Woops")

                for datapoint in data[KEY_PROVIDERS]:
                    try:
                        if datapoint[KEY_PROVIDER] == provider:
                            provider_data = datapoint
                            break
                    except KeyError as k:
                        raise KeyError("The config file has malformed keys") from k
                # Verify SHA value
                manifest_file = f"{self.project_root}/test/artifacts/{provider_data[KEY_FILE]}"

                if verify_sha256(file, provider_data[KEY_BSHA256]):
                    print("success - sha checksum match")
                else:
                    raise ValueError("SHA256 manifest verification failed for {provider}")
                manifest_cert_count = provider_data[KEY_COUNT]


            test_start = time.time()
            try:
                success = test_functions[provider](manifest_path=manifest_file,
                                                   manifest_cert_count=manifest_cert_count)
                test_duration = (time.time() - test_start) * 1000

                self.test_results[provider] = {
                    'success': success,
                    'duration_ms': test_duration,
                    'error': None if success else 'Test failed - check logs above'
                }

            except Exception as e:
                test_duration = (time.time() - test_start) * 1000
                print(f"❌ Exception in {provider} test: {e}")

                self.test_results[provider] = {
                    'success': False,
                    'duration_ms': test_duration,
                    'error': str(e)
                }

        # Generate final report
        return self._generate_final_report()

    def _generate_final_report(self) -> Dict:
        """Generate comprehensive test report"""

        end_time = datetime.now()
        total_duration = (end_time - self.start_time).total_seconds() * 1000

        # Calculate summary statistics
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results.values() if result['success'])
        failed_tests = total_tests - passed_tests

        success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0

        report = {
            'test_suite': 'End-to-End Integration Tests',
            'start_time': self.start_time.isoformat(),
            'end_time': end_time.isoformat(),
            'total_duration_ms': total_duration,
            'summary': {
                'total_tests': total_tests,
                'passed': passed_tests,
                'failed': failed_tests,
                'success_rate': success_rate
            },
            'results': self.test_results,
            'overall_success': failed_tests == 0
        }

        # Print final report
        self._print_final_report(report)

        return report

    def _print_final_report(self, report: Dict):
        """Print formatted final report"""

        print("\n" + "=" * 100)
        print("🎯 END-TO-END INTEGRATION TEST SUITE RESULTS")
        print("=" * 100)

        # Summary
        summary = report['summary']
        print("📊 Test Summary:")
        print(f"   Total Tests: {summary['total_tests']}")
        print(f"   Passed: ✅ {summary['passed']}")
        print(f"   Failed: ❌ {summary['failed']}")
        print(f"   Success Rate: {summary['success_rate']:.1f}%")
        print(f"   Total Duration: {report['total_duration_ms']/1000:.1f}s")

        # Individual results
        print("\n📋 Individual Test Results:")
        for provider, result in report['results'].items():
            status = "✅ PASSED" if result['success'] else "❌ FAILED"
            duration = result['duration_ms'] / 1000
            print(f"   {provider.upper():12} | {status:10} | {duration:8.1f}s")

            if result['error']:
                print(f"                    Error: {result['error']}")

        # Overall result
        overall_status = "🎉 ALL TESTS PASSED" if report['overall_success'] else "❌ SOME TESTS FAILED"
        print(f"\n🏆 Overall Result: {overall_status}")

        # Next steps
        if report['overall_success']:
            print("\n✅ End-to-end integration testing complete!")
            print("   🎯 All Thingpress providers are working correctly")
            print("   🚀 System is ready for production use")
            print("   📋 Certificate deployer integration verified")
        else:
            print("\n⚠️  Some end-to-end tests failed.")
            print("   🔍 Review the detailed results above")
            print("   🛠️  Fix failing providers before release")
            print("   📞 Consider investigating system-level issues")

        print("=" * 100)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Run Thingpress end-to-end integration tests')
    parser.add_argument(
        '--providers', 
        nargs='+', 
        choices=['microchip', 'espressif', 'infineon', 'generated', 'all'],
        default=['all'],
        help='Providers to test (default: all)'
    )
    parser.add_argument(
        '--output-file',
        help='Save test results to JSON file'
    )
    parser.add_argument(
        '--quick',
        action='store_true',
        help='Run with shorter timeouts for quicker feedback'
    )

    args = parser.parse_args()

    # Handle 'all' option
    if 'all' in args.providers:
        providers = ['microchip', 'espressif', 'infineon', 'generated']
    else:
        providers = args.providers

    # Run tests
    runner = EndToEndTestRunner()
    report = runner.run_all_tests(providers)

    # Save results if requested
    if args.output_file:
        with open(args.output_file, 'w') as f:
            json.dump(report, f, indent=2)
        print(f"\n💾 Test results saved to: {args.output_file}")

    # Exit with appropriate code
    exit_code = 0 if report['overall_success'] else 1
    sys.exit(exit_code)


if __name__ == "__main__":
    main()

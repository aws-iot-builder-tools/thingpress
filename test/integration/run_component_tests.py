#!/usr/bin/env python3
"""
Component Integration Test Runner

Runs all provider component tests and generates a comprehensive report.
This is the main entry point for component testing.
"""

import os
import sys
import json
import time
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Dict

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))
sys.path.append(str(project_root / 'test/integration'))

# Import test modules
from component.test_microchip_provider import run_microchip_component_test
from component.test_espressif_provider import run_espressif_component_test
from component.test_infineon_provider import run_infineon_component_test
from component.test_generated_provider import run_generated_component_test


class ComponentTestRunner:
    """Runs and manages component integration tests"""
    
    def __init__(self):
        self.test_results = {}
        self.start_time = datetime.now()
        
    def run_all_tests(self, providers: List[str] = None) -> Dict:
        """Run component tests for specified providers"""
        
        # Default to all providers if none specified
        if providers is None:
            providers = ['microchip', 'espressif', 'infineon', 'generated']
            
        print("🚀 Starting Component Integration Test Suite")
        print("=" * 60)
        print(f"Providers to test: {', '.join(providers)}")
        print(f"Start time: {self.start_time.isoformat()}")
        print("=" * 60)
        
        # Test functions mapping
        test_functions = {
            'microchip': run_microchip_component_test,
            'espressif': run_espressif_component_test,
            'infineon': run_infineon_component_test,
            'generated': run_generated_component_test
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
                
            print(f"\n🧪 Testing {provider.upper()} Provider...")
            print("-" * 40)
            
            test_start = time.time()
            try:
                success = test_functions[provider]()
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
            'test_suite': 'Component Integration Tests',
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
        
        print("\n" + "=" * 80)
        print("🎯 COMPONENT INTEGRATION TEST SUITE RESULTS")
        print("=" * 80)
        
        # Summary
        summary = report['summary']
        print(f"📊 Test Summary:")
        print(f"   Total Tests: {summary['total_tests']}")
        print(f"   Passed: ✅ {summary['passed']}")
        print(f"   Failed: ❌ {summary['failed']}")
        print(f"   Success Rate: {summary['success_rate']:.1f}%")
        print(f"   Total Duration: {report['total_duration_ms']:.2f}ms")
        
        # Individual results
        print(f"\n📋 Individual Test Results:")
        for provider, result in report['results'].items():
            status = "✅ PASSED" if result['success'] else "❌ FAILED"
            duration = result['duration_ms']
            print(f"   {provider.upper():12} | {status:10} | {duration:8.2f}ms")
            
            if result['error']:
                print(f"                    Error: {result['error']}")
                
        # Overall result
        overall_status = "🎉 ALL TESTS PASSED" if report['overall_success'] else "❌ SOME TESTS FAILED"
        print(f"\n🏆 Overall Result: {overall_status}")
        
        # Next steps
        if report['overall_success']:
            print("\n✅ Component testing complete! All providers are working correctly.")
            print("   Ready to proceed with end-to-end integration testing.")
        else:
            print("\n⚠️  Some component tests failed. Please review the errors above.")
            print("   Fix the failing components before proceeding to end-to-end testing.")
            
        print("=" * 80)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Run Thingpress component integration tests')
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
    
    args = parser.parse_args()
    
    # Handle 'all' option
    if 'all' in args.providers:
        providers = ['microchip', 'espressif', 'infineon', 'generated']
    else:
        providers = args.providers
        
    # Run tests
    runner = ComponentTestRunner()
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

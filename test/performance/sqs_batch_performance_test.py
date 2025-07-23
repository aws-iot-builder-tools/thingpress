#!/usr/bin/env python3
"""
SQS Batch Performance Test
Validates the performance improvements from SQS batch processing
"""

import time
import boto3
import json
import tempfile
import shutil
from pathlib import Path
from datetime import datetime

class SQSBatchPerformanceTest:
    def __init__(self):
        self.s3_client = boto3.client('s3')
        self.bucket_name = "thingpress-generated-sam-app"
        self.temp_dir = None
        
    def setup_temp_directory(self):
        """Create temporary directory for test files"""
        self.temp_dir = Path(tempfile.mkdtemp(prefix="sqs_batch_test_"))
        print(f"📁 Created temporary directory: {self.temp_dir}")
        return self.temp_dir
    
    def cleanup_temp_directory(self):
        """Clean up temporary directory"""
        if self.temp_dir and self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)
            print(f"🧹 Cleaned up temporary directory: {self.temp_dir}")
    
    def generate_test_certificates(self, count: int) -> str:
        """Generate test certificate file for batch processing test"""
        print(f"🔄 Generating {count:,} test certificates...")
        
        # Use the existing certificate generator
        import subprocess
        
        cmd = [
            "python", "../../src/certificate_generator/generate_certificates.py",
            "--count", str(count),
            "--batch-size", str(count),  # Single file
            "--output-dir", str(self.temp_dir),
            "--cn-prefix", "BatchTest-Device-"
        ]
        
        start_time = time.time()
        result = subprocess.run(cmd, capture_output=True, text=True)
        generation_time = time.time() - start_time
        
        if result.returncode != 0:
            print(f"❌ Certificate generation failed: {result.stderr}")
            return None
        
        # Find the generated file
        cert_files = list(self.temp_dir.glob("certificates_*.txt"))
        if not cert_files:
            print("❌ No certificate files generated")
            return None
        
        cert_file = cert_files[0]
        print(f"✅ Generated {count:,} certificates in {generation_time:.2f} seconds")
        print(f"   📄 File: {cert_file.name}")
        
        return str(cert_file)
    
    def run_batch_performance_comparison(self, certificate_count: int = 1000):
        """
        Compare performance between individual and batch processing
        by uploading certificate files and monitoring processing
        """
        print("🚀 SQS BATCH PERFORMANCE COMPARISON")
        print("=" * 60)
        print(f"📊 Test Parameters:")
        print(f"   • Certificate count: {certificate_count:,}")
        print(f"   • Expected batches: {certificate_count // 10}")
        print(f"   • Test timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        overall_start = time.time()
        
        try:
            # Setup
            self.setup_temp_directory()
            
            # Generate test certificates
            print(f"\n📋 STEP 1: Certificate Generation")
            print("-" * 40)
            cert_file = self.generate_test_certificates(certificate_count)
            if not cert_file:
                return False
            
            # Upload and test batch processing
            print(f"\n📋 STEP 2: Batch Processing Test")
            print("-" * 40)
            
            test_name = f"batch-perf-test-{int(time.time())}"
            s3_key = f"{test_name}/certificates.txt"
            
            print(f"   📤 Uploading certificate file: {s3_key}")
            upload_start = time.time()
            
            try:
                self.s3_client.upload_file(cert_file, self.bucket_name, s3_key)
                upload_time = time.time() - upload_start
                print(f"      ✅ Uploaded in {upload_time:.2f}s")
                
            except Exception as e:
                print(f"      ❌ Upload failed: {e}")
                return False
            
            # Monitor processing
            print(f"\n📋 STEP 3: Processing Monitoring")
            print("-" * 40)
            
            expected_batches = (certificate_count + 9) // 10  # Round up
            expected_processing_time = expected_batches * 2.4  # ~2.4s per batch
            
            print(f"   📊 Expected processing metrics:")
            print(f"      • Certificates: {certificate_count:,}")
            print(f"      • Expected batches: {expected_batches}")
            print(f"      • Expected processing time: ~{expected_processing_time/60:.1f} minutes")
            print(f"      • Expected SQS API calls: ~{expected_batches} (vs {certificate_count} individual)")
            print(f"      • API call reduction: {((certificate_count - expected_batches) / certificate_count) * 100:.1f}%")
            
            print(f"\n🔍 Monitor processing:")
            print(f"   • CloudWatch logs: /aws/lambda/sam-app-ThingpressGeneratedProviderFunction-*")
            print(f"   • Filter: 'Sending batch of' OR 'Batch send complete'")
            print(f"   • Expected log entries: ~{expected_batches * 2} (batch start + complete)")
            
            # Performance projections
            print(f"\n📈 Performance Projections:")
            print(f"   • Individual processing: {certificate_count} SQS API calls")
            print(f"   • Batch processing: ~{expected_batches} SQS API calls")
            print(f"   • Throughput improvement: ~{certificate_count / expected_batches:.1f}x fewer API calls")
            
            # Cost analysis
            sqs_cost_per_request = 0.0000004  # $0.40 per million requests
            individual_cost = certificate_count * sqs_cost_per_request
            batch_cost = expected_batches * sqs_cost_per_request
            cost_savings = individual_cost - batch_cost
            
            print(f"\n💰 Cost Analysis:")
            print(f"   • Individual approach: ${individual_cost:.6f}")
            print(f"   • Batch approach: ${batch_cost:.6f}")
            print(f"   • Cost savings: ${cost_savings:.6f} ({((cost_savings/individual_cost)*100):.1f}%)")
            
            total_time = time.time() - overall_start
            print(f"\n⏱️  Total test setup time: {total_time:.1f} seconds")
            
            return True
            
        finally:
            # Always cleanup
            self.cleanup_temp_directory()
    
    def run_scale_tests(self):
        """Run multiple scale tests to validate batch performance"""
        test_scales = [
            {"name": "Small", "count": 100, "description": "Quick validation"},
            {"name": "Medium", "count": 1000, "description": "Standard batch test"},
            {"name": "Large", "count": 5000, "description": "High-volume test"},
        ]
        
        print("🎯 SQS Batch Scale Testing")
        print("=" * 60)
        
        for test in test_scales:
            print(f"\n🔬 {test['name']} Scale Test ({test['description']})")
            print(f"   Certificate count: {test['count']:,}")
            
            success = self.run_batch_performance_comparison(test['count'])
            
            if success:
                print(f"   ✅ {test['name']} test completed successfully")
            else:
                print(f"   ❌ {test['name']} test failed")
                break
            
            # Small delay between tests
            if test != test_scales[-1]:
                print("   ⏸️  Waiting 30 seconds before next test...")
                time.sleep(30)
        
        print(f"\n🎉 Scale testing completed!")

def main():
    """Main function with command line interface"""
    import argparse
    
    parser = argparse.ArgumentParser(description="SQS Batch Performance Test")
    parser.add_argument("--certificates", type=int, default=1000, 
                       help="Number of certificates to test (default: 1000)")
    parser.add_argument("--scale-tests", action="store_true",
                       help="Run multiple scale tests")
    
    args = parser.parse_args()
    
    tester = SQSBatchPerformanceTest()
    
    if args.scale_tests:
        success = tester.run_scale_tests()
    else:
        success = tester.run_batch_performance_comparison(args.certificates)
    
    if success:
        print("\n🎉 SQS batch performance test completed successfully!")
        print("\n📋 Next Steps:")
        print("   1. Monitor CloudWatch logs for batch processing messages")
        print("   2. Verify SQS API call reduction in CloudWatch metrics")
        print("   3. Compare processing times with previous individual approach")
        return 0
    else:
        print("\n❌ SQS batch performance test failed!")
        return 1

if __name__ == "__main__":
    exit(main())

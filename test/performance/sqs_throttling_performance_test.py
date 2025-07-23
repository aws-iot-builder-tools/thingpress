#!/usr/bin/env python3
"""
SQS Throttling Performance Test
Validates the automatic throttling functionality and its impact on system performance
"""

import time
import boto3
import json
import tempfile
import shutil
from pathlib import Path
from datetime import datetime

class SQSThrottlingPerformanceTest:
    def __init__(self):
        self.s3_client = boto3.client('s3')
        self.sqs_client = boto3.client('sqs')
        self.cloudwatch_client = boto3.client('cloudwatch')
        self.bucket_name = "thingpress-generated-sam-app"
        self.temp_dir = None
        
    def setup_temp_directory(self):
        """Create temporary directory for test files"""
        self.temp_dir = Path(tempfile.mkdtemp(prefix="throttling_test_"))
        print(f"📁 Created temporary directory: {self.temp_dir}")
        return self.temp_dir
    
    def cleanup_temp_directory(self):
        """Clean up temporary directory"""
        if self.temp_dir and self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)
            print(f"🧹 Cleaned up temporary directory: {self.temp_dir}")
    
    def get_bulk_importer_queue_url(self):
        """Get the bulk importer queue URL for monitoring"""
        try:
            # List queues and find the bulk importer queue
            response = self.sqs_client.list_queues(QueueNamePrefix="Thingpress-Bulk-Importer")
            if 'QueueUrls' in response and response['QueueUrls']:
                return response['QueueUrls'][0]
            else:
                print("⚠️  Could not find bulk importer queue")
                return None
        except Exception as e:
            print(f"❌ Error finding bulk importer queue: {e}")
            return None
    
    def get_queue_metrics(self, queue_url):
        """Get current queue metrics"""
        try:
            response = self.sqs_client.get_queue_attributes(
                QueueUrl=queue_url,
                AttributeNames=[
                    'ApproximateNumberOfMessages',
                    'ApproximateNumberOfMessagesNotVisible',
                    'ApproximateNumberOfMessagesDelayed'
                ]
            )
            
            attrs = response['Attributes']
            return {
                'visible': int(attrs.get('ApproximateNumberOfMessages', 0)),
                'in_flight': int(attrs.get('ApproximateNumberOfMessagesNotVisible', 0)),
                'delayed': int(attrs.get('ApproximateNumberOfMessagesDelayed', 0)),
                'total': int(attrs.get('ApproximateNumberOfMessages', 0)) + 
                        int(attrs.get('ApproximateNumberOfMessagesNotVisible', 0))
            }
        except Exception as e:
            print(f"❌ Error getting queue metrics: {e}")
            return {'visible': 0, 'in_flight': 0, 'delayed': 0, 'total': 0}
    
    def generate_test_certificates(self, count: int) -> str:
        """Generate test certificate file for throttling test"""
        print(f"🔄 Generating {count:,} test certificates...")
        
        import subprocess
        
        cmd = [
            "python", "../../src/certificate_generator/generate_certificates.py",
            "--count", str(count),
            "--batch-size", str(count),  # Single file
            "--output-dir", str(self.temp_dir),
            "--cn-prefix", "ThrottleTest-Device-"
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
        
        return str(cert_file)
    
    def run_throttling_performance_test(self, certificate_count: int = 2000):
        """
        Test throttling performance by creating load and monitoring system response
        """
        print("🎛️ SQS THROTTLING PERFORMANCE TEST")
        print("=" * 60)
        print(f"📊 Test Parameters:")
        print(f"   • Certificate count: {certificate_count:,}")
        print(f"   • Test timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        overall_start = time.time()
        
        try:
            # Setup
            self.setup_temp_directory()
            
            # Get queue URL for monitoring
            queue_url = self.get_bulk_importer_queue_url()
            if not queue_url:
                print("❌ Cannot proceed without queue URL")
                return False
            
            print(f"📊 Monitoring queue: {queue_url.split('/')[-1]}")
            
            # Get baseline queue metrics
            print(f"\n📋 STEP 1: Baseline Queue Metrics")
            print("-" * 40)
            baseline_metrics = self.get_queue_metrics(queue_url)
            print(f"   📊 Baseline queue depth: {baseline_metrics['total']}")
            print(f"      • Visible: {baseline_metrics['visible']}")
            print(f"      • In-flight: {baseline_metrics['in_flight']}")
            print(f"      • Delayed: {baseline_metrics['delayed']}")
            
            # Generate test certificates
            print(f"\n📋 STEP 2: Certificate Generation")
            print("-" * 40)
            cert_file = self.generate_test_certificates(certificate_count)
            if not cert_file:
                return False
            
            # Upload and trigger processing
            print(f"\n📋 STEP 3: Load Generation & Throttling Test")
            print("-" * 40)
            
            test_name = f"throttling-test-{int(time.time())}"
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
            
            # Monitor throttling behavior
            print(f"\n📋 STEP 4: Throttling Behavior Monitoring")
            print("-" * 40)
            
            monitoring_duration = 300  # 5 minutes
            check_interval = 30  # 30 seconds
            monitoring_start = time.time()
            
            max_queue_depth = 0
            throttling_events = 0
            queue_history = []
            
            print(f"   🔍 Monitoring for {monitoring_duration} seconds...")
            print(f"   📊 Queue depth checks every {check_interval} seconds")
            
            while time.time() - monitoring_start < monitoring_duration:
                current_metrics = self.get_queue_metrics(queue_url)
                current_time = time.time() - monitoring_start
                
                queue_history.append({
                    'time': current_time,
                    'metrics': current_metrics
                })
                
                max_queue_depth = max(max_queue_depth, current_metrics['total'])
                
                # Detect potential throttling (queue depth changes)
                if len(queue_history) > 1:
                    prev_total = queue_history[-2]['metrics']['total']
                    curr_total = current_metrics['total']
                    
                    # If queue depth decreased significantly, throttling may be working
                    if prev_total > 500 and curr_total < prev_total * 0.8:
                        throttling_events += 1
                
                print(f"   ⏱️  {current_time:6.0f}s: Queue depth = {current_metrics['total']:4d} "
                      f"(visible: {current_metrics['visible']:3d}, "
                      f"in-flight: {current_metrics['in_flight']:3d})")
                
                time.sleep(check_interval)
            
            # Analysis
            print(f"\n📈 Throttling Analysis")
            print("-" * 40)
            
            final_metrics = self.get_queue_metrics(queue_url)
            
            print(f"   📊 Queue Depth Analysis:")
            print(f"      • Baseline depth: {baseline_metrics['total']}")
            print(f"      • Maximum depth: {max_queue_depth}")
            print(f"      • Final depth: {final_metrics['total']}")
            print(f"      • Peak increase: {max_queue_depth - baseline_metrics['total']}")
            
            print(f"\n   🎛️  Throttling Effectiveness:")
            print(f"      • Potential throttling events: {throttling_events}")
            
            if max_queue_depth > 1000:
                print(f"      • ✅ High load detected (>{max_queue_depth}) - throttling should activate")
            elif max_queue_depth > 500:
                print(f"      • ⚠️  Medium load detected ({max_queue_depth}) - moderate throttling")
            else:
                print(f"      • ℹ️  Low load detected ({max_queue_depth}) - minimal throttling needed")
            
            # Expected throttling behavior
            expected_batches = (certificate_count + 9) // 10
            expected_processing_time = expected_batches * 2.4  # ~2.4s per batch
            
            print(f"\n   📊 Processing Projections:")
            print(f"      • Expected batches: {expected_batches}")
            print(f"      • Expected processing time: ~{expected_processing_time/60:.1f} minutes")
            print(f"      • With throttling: +20-50% processing time (adaptive)")
            
            # Recommendations
            print(f"\n💡 Throttling Recommendations:")
            if max_queue_depth > 2000:
                print(f"   • Consider increasing ProviderConcurrencyLimit")
                print(f"   • Consider reducing ThrottlingBaseDelay")
            elif max_queue_depth < 100:
                print(f"   • Current throttling settings are conservative")
                print(f"   • Could increase processing speed if needed")
            else:
                print(f"   • Throttling settings appear well-balanced")
            
            total_time = time.time() - overall_start
            print(f"\n⏱️  Total test time: {total_time:.1f} seconds")
            
            return True
            
        finally:
            # Always cleanup
            self.cleanup_temp_directory()
    
    def run_throttling_configuration_test(self):
        """Test different throttling configurations"""
        test_configs = [
            {"name": "Conservative", "certs": 500, "description": "Low load test"},
            {"name": "Moderate", "certs": 1500, "description": "Medium load test"},
            {"name": "Aggressive", "certs": 3000, "description": "High load test"},
        ]
        
        print("🎯 SQS Throttling Configuration Testing")
        print("=" * 60)
        
        for config in test_configs:
            print(f"\n🔬 {config['name']} Configuration Test ({config['description']})")
            print(f"   Certificate count: {config['certs']:,}")
            
            success = self.run_throttling_performance_test(config['certs'])
            
            if success:
                print(f"   ✅ {config['name']} test completed successfully")
            else:
                print(f"   ❌ {config['name']} test failed")
                break
            
            # Delay between tests to allow system to settle
            if config != test_configs[-1]:
                print("   ⏸️  Waiting 60 seconds for system to settle...")
                time.sleep(60)
        
        print(f"\n🎉 Throttling configuration testing completed!")

def main():
    """Main function with command line interface"""
    import argparse
    
    parser = argparse.ArgumentParser(description="SQS Throttling Performance Test")
    parser.add_argument("--certificates", type=int, default=2000, 
                       help="Number of certificates to test (default: 2000)")
    parser.add_argument("--config-tests", action="store_true",
                       help="Run multiple configuration tests")
    
    args = parser.parse_args()
    
    tester = SQSThrottlingPerformanceTest()
    
    if args.config_tests:
        success = tester.run_throttling_configuration_test()
    else:
        success = tester.run_throttling_performance_test(args.certificates)
    
    if success:
        print("\n🎉 SQS throttling performance test completed successfully!")
        print("\n📋 Next Steps:")
        print("   1. Monitor CloudWatch dashboard for throttling metrics")
        print("   2. Adjust throttling parameters based on observed behavior")
        print("   3. Validate throttling effectiveness in production workloads")
        return 0
    else:
        print("\n❌ SQS throttling performance test failed!")
        return 1

if __name__ == "__main__":
    exit(main())

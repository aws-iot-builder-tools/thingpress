#!/usr/bin/env python3
"""
Integrated Performance Test for Thingpress
Generates certificates on-demand and runs performance tests
No large files committed to git - everything generated fresh
"""

import os
import time
import boto3
import subprocess
import tempfile
import shutil
from datetime import datetime
from pathlib import Path

class IntegratedPerformanceTest:
    def __init__(self):
        self.s3_client = boto3.client('s3')
        self.bucket_name = "thingpress-generated-sam-app"
        self.temp_dir = None
        
    def setup_temp_directory(self):
        """Create temporary directory for test files"""
        self.temp_dir = Path(tempfile.mkdtemp(prefix="thingpress_perf_"))
        print(f"📁 Created temporary directory: {self.temp_dir}")
        return self.temp_dir
    
    def cleanup_temp_directory(self):
        """Clean up temporary directory"""
        if self.temp_dir and self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)
            print(f"🧹 Cleaned up temporary directory: {self.temp_dir}")
    
    def generate_certificates(self, total_count, batch_size=1000):
        """Generate certificates on-demand using the certificate generator"""
        print(f"🔄 Generating {total_count:,} certificates in {batch_size}-certificate batches...")
        
        # Use the existing certificate generator (adjust path for new location)
        cmd = [
            "python", "../../src/certificate_generator/generate_certificates.py",
            "--count", str(total_count),
            "--batch-size", str(batch_size),
            "--output-dir", str(self.temp_dir),
            "--cn-prefix", "PerfTest-Device-"
        ]
        
        start_time = time.time()
        result = subprocess.run(cmd, capture_output=True, text=True)
        generation_time = time.time() - start_time
        
        if result.returncode != 0:
            print(f"❌ Certificate generation failed: {result.stderr}")
            return False, 0
        
        # Count generated batch files
        batch_files = list(self.temp_dir.glob("certificates_*_batch_*.txt"))
        
        print(f"✅ Generated {len(batch_files)} batch files in {generation_time:.2f} seconds")
        print(f"   📊 Generation rate: {total_count/generation_time:.0f} certificates/second")
        
        return True, len(batch_files)
    
    def run_performance_test(self, total_certificates=50000, batch_size=1000, test_name="integrated-perf"):
        """Run complete performance test with on-demand certificate generation"""
        print("🚀 INTEGRATED THINGPRESS PERFORMANCE TEST")
        print("=" * 60)
        print(f"📊 Test Parameters:")
        print(f"   • Total certificates: {total_certificates:,}")
        print(f"   • Batch size: {batch_size}")
        print(f"   • Expected batches: {total_certificates // batch_size}")
        print(f"   • Test name: {test_name}")
        
        overall_start = time.time()
        
        try:
            # Step 1: Setup
            self.setup_temp_directory()
            
            # Step 2: Generate certificates
            print(f"\n📋 STEP 1: Certificate Generation")
            print("-" * 40)
            success, num_batches = self.generate_certificates(total_certificates, batch_size)
            if not success:
                return False
            
            # Step 3: Upload and test
            print(f"\n📋 STEP 2: Upload and Processing Test")
            print("-" * 40)
            
            batch_files = sorted(list(self.temp_dir.glob("certificates_*_batch_*.txt")))
            upload_times = []
            successful_uploads = 0
            
            upload_start = time.time()
            
            for i, batch_file in enumerate(batch_files):
                batch_num = i + 1
                print(f"   📤 Uploading batch {batch_num}/{num_batches}: {batch_file.name}")
                
                file_upload_start = time.time()
                s3_key = f"{test_name}/batch_{batch_num:03d}.txt"
                
                try:
                    self.s3_client.upload_file(str(batch_file), self.bucket_name, s3_key)
                    upload_time = time.time() - file_upload_start
                    upload_times.append(upload_time)
                    successful_uploads += 1
                    
                    print(f"      ✅ Uploaded in {upload_time:.2f}s")
                    
                    # Small delay to avoid overwhelming the system
                    if i < len(batch_files) - 1:
                        time.sleep(1)
                        
                except Exception as e:
                    print(f"      ❌ Upload failed: {e}")
                    continue
            
            upload_total_time = time.time() - upload_start
            
            # Step 4: Results
            print(f"\n📋 STEP 3: Results Summary")
            print("-" * 40)
            
            total_time = time.time() - overall_start
            processed_certs = successful_uploads * batch_size
            
            print(f"⏱️  Total test time: {total_time/60:.1f} minutes")
            print(f"   • Certificate generation: {(upload_start - overall_start):.1f} seconds")
            print(f"   • Upload phase: {upload_total_time:.1f} seconds")
            
            print(f"📊 Certificate metrics:")
            print(f"   • Certificates processed: {processed_certs:,}")
            print(f"   • Batches uploaded: {successful_uploads}/{num_batches}")
            print(f"   • Upload success rate: {(successful_uploads/num_batches)*100:.1f}%")
            
            if upload_times:
                avg_upload = sum(upload_times) / len(upload_times)
                print(f"📤 Upload performance:")
                print(f"   • Average upload time: {avg_upload:.2f}s per batch")
                print(f"   • Upload throughput: {processed_certs/upload_total_time:.0f} certs/second")
            
            print(f"\n🔍 Monitor processing:")
            print(f"   • Expected processing time: ~{successful_uploads * 2.4/60:.1f} minutes")
            print(f"   • CloudWatch logs: /aws/lambda/sam-app-ThingpressGeneratedProviderFunction-*")
            print(f"   • Filter: 'Total certificates processed'")
            
            return True
            
        finally:
            # Always cleanup
            self.cleanup_temp_directory()
    
    def run_scale_test(self, scale="medium"):
        """Run predefined scale tests"""
        scale_configs = {
            "small": {"certs": 5000, "batch_size": 1000, "name": "small-scale-5k"},
            "medium": {"certs": 25000, "batch_size": 1000, "name": "medium-scale-25k"}, 
            "large": {"certs": 100000, "batch_size": 1000, "name": "large-scale-100k"},
            "xlarge": {"certs": 200000, "batch_size": 1000, "name": "xlarge-scale-200k"}
        }
        
        if scale not in scale_configs:
            print(f"❌ Unknown scale '{scale}'. Available: {list(scale_configs.keys())}")
            return False
        
        config = scale_configs[scale]
        print(f"🎯 Running {scale} scale test...")
        
        return self.run_performance_test(
            total_certificates=config["certs"],
            batch_size=config["batch_size"], 
            test_name=config["name"]
        )

def main():
    """Main function with command line interface"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Integrated Thingpress Performance Test")
    parser.add_argument("--scale", choices=["small", "medium", "large", "xlarge"], 
                       default="medium", help="Test scale to run")
    parser.add_argument("--certificates", type=int, help="Custom number of certificates")
    parser.add_argument("--batch-size", type=int, default=1000, help="Certificates per batch")
    
    args = parser.parse_args()
    
    tester = IntegratedPerformanceTest()
    
    if args.certificates:
        # Custom test
        success = tester.run_performance_test(
            total_certificates=args.certificates,
            batch_size=args.batch_size,
            test_name=f"custom-{args.certificates}"
        )
    else:
        # Predefined scale test
        success = tester.run_scale_test(args.scale)
    
    if success:
        print("\n🎉 Performance test completed successfully!")
        return 0
    else:
        print("\n❌ Performance test failed!")
        return 1

if __name__ == "__main__":
    exit(main())

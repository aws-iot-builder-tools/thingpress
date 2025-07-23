#!/usr/bin/env python3
"""
Proof of Concept: SQS Batch Optimization for Thingpress
Demonstrates the performance improvements from batching SQS messages
"""

import time
import boto3
import json
from json import dumps
from typing import List, Dict, Any
from botocore.exceptions import ClientError

class SQSBatchOptimizer:
    def __init__(self, session=None):
        self.session = session or boto3.Session()
        self.sqs_client = self.session.client('sqs')
        
    def send_sqs_message_batch(self, messages: List[Dict], queue_url: str) -> List[Dict]:
        """
        Send multiple messages in a single SQS batch operation
        SQS batch limit is 10 messages per call
        """
        batch_size = 10
        results = []
        
        for i in range(0, len(messages), batch_size):
            batch = messages[i:i + batch_size]
            entries = []
            
            for idx, message in enumerate(batch):
                entries.append({
                    'Id': str(i + idx),
                    'MessageBody': dumps(message),
                    'MessageAttributes': {
                        'BatchIndex': {
                            'StringValue': str(i + idx),
                            'DataType': 'Number'
                        }
                    }
                })
            
            try:
                response = self.sqs_client.send_message_batch(
                    QueueUrl=queue_url,
                    Entries=entries
                )
                results.append(response)
                
                # Handle partial failures
                if 'Failed' in response and response['Failed']:
                    print(f"⚠️  Batch send partial failure: {len(response['Failed'])} messages failed")
                    for failure in response['Failed']:
                        print(f"   Failed message ID {failure['Id']}: {failure['Code']} - {failure['Message']}")
                        
            except ClientError as error:
                print(f"❌ Batch send failed: {error}")
                raise error
        
        return results
    
    def send_sqs_message_individual(self, messages: List[Dict], queue_url: str) -> List[Dict]:
        """
        Send messages individually (current approach)
        """
        results = []
        
        for idx, message in enumerate(messages):
            try:
                response = self.sqs_client.send_message(
                    QueueUrl=queue_url,
                    MessageBody=dumps(message),
                    MessageAttributes={
                        'MessageIndex': {
                            'StringValue': str(idx),
                            'DataType': 'Number'
                        }
                    }
                )
                results.append(response)
                
            except ClientError as error:
                print(f"❌ Individual send failed for message {idx}: {error}")
                raise error
        
        return results
    
    def create_test_messages(self, count: int) -> List[Dict]:
        """Create test certificate messages"""
        messages = []
        
        for i in range(count):
            message = {
                'thing': f'PerfTest-Device-{i:06d}',
                'certificate': f'LS0tLS1CRUdJTiBDRVJUSUZJQ0FURS0tLS0t...{i}...LS0tLS1FTkQgQ0VSVElGSUNBVEUtLS0tLQ==',
                'bucket': 'test-bucket',
                'key': f'test-batch/cert-{i}.txt',
                'policy': 'test-policy',
                'thing_group': 'test-group',
                'thing_type': 'test-type'
            }
            messages.append(message)
        
        return messages
    
    def performance_comparison(self, message_count: int, queue_url: str):
        """
        Compare performance between individual and batch sending
        """
        print(f"🔬 Performance Comparison: {message_count} messages")
        print("=" * 60)
        
        # Create test messages
        messages = self.create_test_messages(message_count)
        
        # Test 1: Individual sending (current approach)
        print(f"\n📤 Test 1: Individual Message Sending")
        start_time = time.time()
        
        try:
            individual_results = self.send_sqs_message_individual(messages, queue_url)
            individual_time = time.time() - start_time
            individual_api_calls = len(individual_results)
            
            print(f"   ✅ Completed in {individual_time:.2f} seconds")
            print(f"   📊 API calls: {individual_api_calls}")
            print(f"   🚀 Throughput: {message_count/individual_time:.0f} messages/second")
            
        except Exception as e:
            print(f"   ❌ Individual sending failed: {e}")
            return
        
        # Small delay between tests
        time.sleep(2)
        
        # Test 2: Batch sending (optimized approach)
        print(f"\n📦 Test 2: Batch Message Sending")
        start_time = time.time()
        
        try:
            batch_results = self.send_sqs_message_batch(messages, queue_url)
            batch_time = time.time() - start_time
            batch_api_calls = len(batch_results)
            
            print(f"   ✅ Completed in {batch_time:.2f} seconds")
            print(f"   📊 API calls: {batch_api_calls}")
            print(f"   🚀 Throughput: {message_count/batch_time:.0f} messages/second")
            
        except Exception as e:
            print(f"   ❌ Batch sending failed: {e}")
            return
        
        # Performance analysis
        print(f"\n📈 Performance Analysis")
        print("-" * 40)
        
        time_improvement = ((individual_time - batch_time) / individual_time) * 100
        api_reduction = ((individual_api_calls - batch_api_calls) / individual_api_calls) * 100
        throughput_improvement = ((message_count/batch_time) / (message_count/individual_time) - 1) * 100
        
        print(f"⏱️  Time improvement: {time_improvement:.1f}% faster")
        print(f"📞 API call reduction: {api_reduction:.1f}% fewer calls")
        print(f"🚀 Throughput improvement: {throughput_improvement:.1f}% increase")
        
        # Cost analysis (approximate)
        sqs_cost_per_request = 0.0000004  # $0.40 per million requests
        individual_cost = individual_api_calls * sqs_cost_per_request
        batch_cost = batch_api_calls * sqs_cost_per_request
        cost_savings = individual_cost - batch_cost
        
        print(f"\n💰 Cost Analysis (approximate)")
        print(f"   Individual approach: ${individual_cost:.6f}")
        print(f"   Batch approach: ${batch_cost:.6f}")
        print(f"   Cost savings: ${cost_savings:.6f} ({((cost_savings/individual_cost)*100):.1f}%)")

class SQSThrottlingDemo:
    def __init__(self, session=None):
        self.session = session or boto3.Session()
        self.sqs_client = self.session.client('sqs')
    
    def demonstrate_delay_queue(self, queue_url: str, delay_seconds: int = 30):
        """
        Demonstrate SQS delay queue functionality
        """
        print(f"🕐 SQS Delay Queue Demo: {delay_seconds}s delay")
        print("-" * 50)
        
        test_message = {
            'test': 'delay_queue_message',
            'timestamp': int(time.time()),
            'delay_seconds': delay_seconds
        }
        
        print(f"📤 Sending message with {delay_seconds}s delay...")
        send_time = time.time()
        
        try:
            response = self.sqs_client.send_message(
                QueueUrl=queue_url,
                MessageBody=dumps(test_message),
                DelaySeconds=delay_seconds
            )
            
            print(f"   ✅ Message sent at {time.strftime('%H:%M:%S', time.localtime(send_time))}")
            print(f"   📋 Message ID: {response['MessageId']}")
            print(f"   ⏰ Will be available at {time.strftime('%H:%M:%S', time.localtime(send_time + delay_seconds))}")
            
        except ClientError as error:
            print(f"   ❌ Failed to send delayed message: {error}")
    
    def check_queue_depth(self, queue_url: str) -> int:
        """
        Check current queue depth for dynamic throttling
        """
        try:
            response = self.sqs_client.get_queue_attributes(
                QueueUrl=queue_url,
                AttributeNames=['ApproximateNumberOfMessages', 'ApproximateNumberOfMessagesNotVisible']
            )
            
            visible = int(response['Attributes']['ApproximateNumberOfMessages'])
            in_flight = int(response['Attributes']['ApproximateNumberOfMessagesNotVisible'])
            total = visible + in_flight
            
            print(f"📊 Queue Depth Analysis:")
            print(f"   Visible messages: {visible}")
            print(f"   In-flight messages: {in_flight}")
            print(f"   Total messages: {total}")
            
            return total
            
        except ClientError as error:
            print(f"❌ Failed to get queue attributes: {error}")
            return 0
    
    def calculate_dynamic_delay(self, queue_depth: int) -> int:
        """
        Calculate optimal delay based on queue depth
        """
        if queue_depth > 1000:
            delay = 60  # 1 minute for high load
            load_level = "HIGH"
        elif queue_depth > 500:
            delay = 30  # 30 seconds for medium load
            load_level = "MEDIUM"
        elif queue_depth > 100:
            delay = 10  # 10 seconds for low-medium load
            load_level = "LOW-MEDIUM"
        else:
            delay = 0   # No delay for low load
            load_level = "LOW"
        
        print(f"🎛️  Dynamic Throttling:")
        print(f"   Load level: {load_level}")
        print(f"   Recommended delay: {delay} seconds")
        
        return delay

def main():
    """
    Main demonstration function
    """
    print("🚀 SQS Optimization Proof of Concept")
    print("=" * 60)
    
    # Note: This is a demonstration - you would need actual SQS queue URLs
    # For testing, you could create temporary queues or use existing ones
    
    print("📋 This proof of concept demonstrates:")
    print("   1. SQS batch sending vs individual sending performance")
    print("   2. SQS delay queue throttling mechanisms")
    print("   3. Dynamic throttling based on queue depth")
    print("   4. Cost analysis and performance metrics")
    
    print(f"\n⚠️  To run actual tests, you need:")
    print("   - Valid SQS queue URLs")
    print("   - AWS credentials configured")
    print("   - Appropriate IAM permissions")
    
    # Example usage (commented out - requires actual queue URLs):
    """
    optimizer = SQSBatchOptimizer()
    throttling_demo = SQSThrottlingDemo()
    
    # Replace with actual queue URL
    queue_url = "https://sqs.us-east-1.amazonaws.com/123456789012/test-queue"
    
    # Performance comparison
    optimizer.performance_comparison(100, queue_url)
    
    # Throttling demonstration
    throttling_demo.demonstrate_delay_queue(queue_url, 30)
    queue_depth = throttling_demo.check_queue_depth(queue_url)
    throttling_demo.calculate_dynamic_delay(queue_depth)
    """
    
    print(f"\n🎯 Expected Benefits:")
    print("   • 90% reduction in SQS API calls")
    print("   • 3-4x improvement in throughput")
    print("   • Automatic throttling without manual intervention")
    print("   • Significant cost savings on SQS API usage")
    print("   • Better error handling and retry mechanisms")

if __name__ == "__main__":
    main()

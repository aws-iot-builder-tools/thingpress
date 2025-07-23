import time
import json
import boto3
import logging
from datetime import datetime

logger = logging.getLogger()
logger.setLevel(logging.INFO)

class TestMetrics:
    """
    Utility class for tracking test metrics and performance.
    """
    
    def __init__(self, test_name):
        """
        Initialize a new TestMetrics instance.
        
        Args:
            test_name (str): Name of the test being executed
        """
        self.test_name = test_name
        self.start_time = datetime.now()
        self.end_time = None
        self.metrics = {
            "test_name": test_name,
            "start_time": self.start_time.isoformat(),
            "steps": [],
            "success": False,
            "error": None
        }
        self.current_step = None
        
    def start_step(self, step_name):
        """
        Start a new test step and record its start time.
        
        Args:
            step_name (str): Name of the step being started
            
        Returns:
            TestMetrics: Self for method chaining
        """
        if self.current_step:
            self.end_step()
            
        self.current_step = {
            "name": step_name,
            "start_time": datetime.now().isoformat(),
            "end_time": None,
            "duration_ms": None,
            "success": False
        }
        logger.info(f"Starting step: {step_name}")
        return self
        
    def end_step(self, success=True):
        """
        End the current step and record metrics.
        
        Args:
            success (bool): Whether the step was successful
            
        Returns:
            TestMetrics: Self for method chaining
        """
        if not self.current_step:
            return self
            
        end_time = datetime.now()
        self.current_step["end_time"] = end_time.isoformat()
        start_time = datetime.fromisoformat(self.current_step["start_time"])
        duration_ms = (end_time - start_time).total_seconds() * 1000
        self.current_step["duration_ms"] = duration_ms
        self.current_step["success"] = success
        
        self.metrics["steps"].append(self.current_step)
        logger.info(f"Completed step: {self.current_step['name']} in {duration_ms:.2f}ms (success: {success})")
        self.current_step = None
        return self
        
    def end_test(self, success=True, error=None):
        """
        End the test and record final metrics.
        
        Args:
            success (bool): Whether the test was successful
            error (Exception, optional): Error that occurred during the test
            
        Returns:
            dict: Test metrics
        """
        if self.current_step:
            self.end_step(success)
            
        self.end_time = datetime.now()
        self.metrics["end_time"] = self.end_time.isoformat()
        self.metrics["duration_ms"] = (self.end_time - self.start_time).total_seconds() * 1000
        self.metrics["success"] = success
        if error:
            self.metrics["error"] = str(error)
            
        logger.info(f"Test completed: {self.test_name} in {self.metrics['duration_ms']:.2f}ms (success: {success})")
        return self.metrics
        
    def save_metrics(self, bucket_name, key_prefix="metrics"):
        """
        Save metrics to S3.
        
        Args:
            bucket_name (str): S3 bucket name
            key_prefix (str, optional): Key prefix for the metrics file
            
        Returns:
            str: S3 key where metrics were saved
        """
        s3 = boto3.client('s3')
        metrics_key = f"{key_prefix}/{self.test_name}_{int(time.time())}.json"
        s3.put_object(
            Bucket=bucket_name,
            Key=metrics_key,
            Body=json.dumps(self.metrics, indent=2),
            ContentType="application/json"
        )
        logger.info(f"Metrics saved to s3://{bucket_name}/{metrics_key}")
        return metrics_key

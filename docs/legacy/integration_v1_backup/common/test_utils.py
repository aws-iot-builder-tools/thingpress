import os
import time
import json
import boto3
import logging
from datetime import datetime

logger = logging.getLogger()
logger.setLevel(logging.INFO)

class TestMetrics:
    def __init__(self, test_name):
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
        """Start a new test step and record its start time."""
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
        """End the current step and record metrics."""
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
        """End the test and record final metrics."""
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
        """Save metrics to S3."""
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

class ResourceCleanup:
    def __init__(self):
        self.resources_to_cleanup = []
        
    def add_s3_object(self, bucket, key):
        """Add S3 object to cleanup list."""
        self.resources_to_cleanup.append(("s3", bucket, key))
        return self
        
    def add_iot_thing(self, thing_name):
        """Add IoT thing to cleanup list."""
        self.resources_to_cleanup.append(("iot_thing", thing_name))
        return self
        
    def add_iot_certificate(self, certificate_id):
        """Add IoT certificate to cleanup list."""
        self.resources_to_cleanup.append(("iot_certificate", certificate_id))
        return self
        
    def cleanup(self):
        """Clean up all registered resources."""
        s3 = boto3.client('s3')
        iot = boto3.client('iot')
        
        for resource_type, *args in self.resources_to_cleanup:
            try:
                if resource_type == "s3":
                    bucket, key = args
                    logger.info(f"Deleting S3 object: s3://{bucket}/{key}")
                    s3.delete_object(Bucket=bucket, Key=key)
                    
                elif resource_type == "iot_thing":
                    thing_name = args[0]
                    logger.info(f"Deleting IoT thing: {thing_name}")
                    # First detach all principals
                    try:
                        principals = iot.list_thing_principals(thingName=thing_name)
                        for principal in principals.get("principals", []):
                            iot.detach_thing_principal(
                                thingName=thing_name,
                                principal=principal
                            )
                    except Exception as e:
                        logger.warning(f"Error detaching principals from thing {thing_name}: {e}")
                    
                    # Then delete the thing
                    iot.delete_thing(thingName=thing_name)
                    
                elif resource_type == "iot_certificate":
                    cert_id = args[0]
                    logger.info(f"Deleting IoT certificate: {cert_id}")
                    # First update to INACTIVE
                    try:
                        iot.update_certificate(
                            certificateId=cert_id,
                            newStatus='INACTIVE'
                        )
                    except Exception as e:
                        logger.warning(f"Error deactivating certificate {cert_id}: {e}")
                    
                    # Then delete
                    iot.delete_certificate(certificateId=cert_id)
                    
            except Exception as e:
                logger.warning(f"Error cleaning up resource {resource_type} {args}: {e}")
                
        self.resources_to_cleanup = []
        logger.info("Resource cleanup completed")

from os import environ
import warnings
with warnings.catch_warnings():
    from boto3 import resource

_LAMBDA_S3_RESOURCE = { "resource" : resource('s3'),
                        "bucket_name" : environ.get("S3_BUCKET_NAME","NONE") }
_LAMBDA_SQS_RESOURCE = { "resource" : resource('sqs'),
                         "queue_name" : environ.get("SQS_QUEUE_NAME","NONE") }

class LambdaSQSClass:
    """
    AWS SQS Resource Class
    """
    def __init__(self, lambda_sqs_resource):  
        """
        Initialize an SQS Resource
        """
        self.resource = lambda_sqs_resource["resource"]
        self.queue_name = lambda_sqs_resource["queue_name"]
        self.queue = self.resource.Queue(self.queue_name)

class LambdaS3Class:
    """
    AWS S3 Resource Class
    """
    def __init__(self, lambda_s3_resource):  
        """
        Initialize an S3 Resource
        """
        self.resource = lambda_s3_resource["resource"]
        self.bucket_name = lambda_s3_resource["bucket_name"]
        self.bucket = self.resource.Bucket(self.bucket_name)

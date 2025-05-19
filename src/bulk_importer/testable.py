from os import environ
import warnings
with warnings.catch_warnings():
    from boto3 import resource

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

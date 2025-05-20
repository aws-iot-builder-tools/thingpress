import os
import io
import json
from botocore import exceptions as botoexceptions
from boto3 import resource as boto3resource, client as boto3client
import binascii
from xml.etree import ElementTree
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from base64 import b64encode

# Given a bucket and object, verify its existence and return the resource.
def s3_object_stream(bucket_name: str, object_name: str):
    s3 = boto3resource('s3')
    res = s3.Object(bucket_name=bucket_name, key=object_name)
    try: 
        fs = io.BytesIO()
        res.download_fileobj(fs)
        return fs
    except botoexceptions.ClientError as ce:
        raise ce

# Given a bucket name and object name, return bytes representing
# the object content.
def s3_filebuf_bytes(bucket_name: str, object_name: str):
    object_stream = s3_object_stream(bucket_name=bucket_name,
                                     object_name=object_name)
    return object_stream.getvalue()

def format_certificate(certString):
    encodedCert = certString.encode('ascii')

    pem_obj = x509.load_pem_x509_certificate(encodedCert,
                                             backend=default_backend())
    block = pem_obj.public_bytes(encoding=serialization.Encoding.PEM).decode('ascii')
    return {'certificate': str(b64encode(block.encode('ascii')))}

    

def invoke_export(manifest, queueUrl):
    client = boto3client("sqs")
    
    root = ElementTree.fromstring(manifest)

    for group in root.findall('group'): # /binaryhex
        thing_name = ''

        for hex_element in group.findall('hex'):
            if hex_element.get('name') == 'TpmMAC':
                thing_name = hex_element.get('value')

        # There can be more than one certificate
        for hexdata_element in group.findall('binaryhex'):
            certificate_data = format_certificate(hexdata_element.text)
            # Need to send each certificate separately
            certificate_data['thing'] = thing_name
            print(certificate_data)
            client.send_message( QueueUrl=queueUrl,
                                 MessageBody=json.dumps(certificate_data) )
        
def lambda_handler(event, context):
    queueUrl = os.environ['QUEUE_TARGET']

    bucket = event['Records'][0]['s3']['bucket']['name']
    manifest = event['Records'][0]['s3']['object']['key'] 

    manifestContent = s3_filebuf_bytes(bucket, manifest)

    invoke_export(manifestContent, queueUrl)

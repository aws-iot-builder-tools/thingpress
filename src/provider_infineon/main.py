import os
import io
import json
import boto3
import binascii
from xml.etree import ElementTree
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from base64 import b64encode

def s3_filebuf_bytes(bucket, obj):
    s3 = boto3.resource('s3')
    bucket = s3.Bucket(bucket)
    obj = bucket.Object(obj)
    file_stream = io.BytesIO()
    obj.download_fileobj(file_stream)
    return file_stream.getvalue()

def format_certificate(der):
    der_raw = ''.join(der.split())
    der_bin = binascii.a2b_hex(der_raw)
    der_enc = der_raw.encode('ascii')
    der_obj = x509.load_der_x509_certificate( der_bin,
                                              backend=default_backend())
    block = der_obj.public_bytes(encoding=serialization.Encoding.PEM).decode('ascii')
    return {'certificate': str(b64encode(block.encode('ascii')))}
    

def invoke_export(manifest, queueUrl):
    client = boto3.client("sqs")
    
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

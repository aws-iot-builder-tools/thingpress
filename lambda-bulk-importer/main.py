# Copyright (C) 2020 Amazon.com, Inc. All Rights Reserved.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of
# this software and associated documentation files (the "Software"), to deal in
# the Software without restriction, including without limitation the rights to
# use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
# the Software, and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
# FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
# COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
# IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

import botocore
import boto3
import base64
import json
import binascii
import os
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

iot_client = boto3.client('iot')

verbose = True

def get_certificate(certificateId):
    try:
        response = iot_client.describe_certificate(certificateId=certificateId)
        return response["certificateDescription"].get("certificateId")
    except:
        print("Certificate [" + certificateId + "] not found in IoT Core.")
        return None

def get_certificate_arn(certificateId):
    try:
        response = iot_client.describe_certificate(certificateId=certificateId)
        return response["certificateDescription"].get("certificateArn")
    except:
        print("Certificate [" + certificateId + "] not found in IoT Core.")
        return None

def get_thing(thingName):
    try:
        response = iot_client.describe_thing(thingName=thingName)
        return response.get("thingArn")
    except:
        print("Thing [" + thingName + "] not found in IoT Core.")
        return None

def get_policy(policyName):
    try:
        response = iot_client.get_policy(policyName=policyName)
        return response.get('policyArn')
    except botocore.exceptions.ClientError as e:
        if error.response['Error']['Code'] == 'ResourceNotFoundException':
            print("ERROR: You need to configure the policy [" + policyName + "] in your target region first.")
        if error.response['Error']['Code'] == 'UnauthorizedException':
            print("ERROR: There is a deployment problem with the attached Role. Unable to reach IoT Core object.")
        return None
    except:
        print("ERROR: Unexpected fault")
        return None

def get_thing_group(thingGroupName):
    try:
        response = iot_client.describe_thing_group(thingGroupName=thingGroupName)
        return response.get('thingGroupArn')
    except botocore.exceptions.ClientError as e:
        if error.response['Error']['Code'] == 'ResourceNotFoundException':
            print("ERROR: You need to configure the Thing Group [" + thingGroupName + "] in your target region first.")
        if error.response['Error']['Code'] == 'UnauthorizedException':
            print("ERROR: There is a deployment problem with the attached Role. Unable to reach IoT Core object.")
        return None
    except:
        print("ERROR: Unexpected fault")
        return None

def get_thing_type(typeName):
    try:
        response = iot_client.describeThingType(thingTypeName=thingTypeName)
        return response.get('thingTypeArn')
    except botocore.exceptions.ClientError as e:
        if error.response['Error']['Code'] == 'ResourceNotFoundException':
            print("ERROR: You need to configure the Thing Type [" + thingTypeName + "] in your target region first.")
        if error.response['Error']['Code'] == 'UnauthorizedException':
            print("ERROR: There is a deployment problem with the attached Role. Unable to reach IoT Core object.")
        return None
    except:
        print("ERROR: Unexpected fault")
        return None

def process_policy(policyName, certificateId):
    iot_client.attach_policy(policyName=policyName,
                             target=get_certificate_arn(certificateId))

def process_thing(thingName, certificateId, thingTypeName):
    certificateArn = get_certificate_arn(certificateId)
    try:
        response = iot_client.describe_thing(thingName=thingName)
        return response.get("thingArn")
    except:
        print("Thing not found. Creating.")
    
    # Create thing
    try:
        if thingTypeName == "":
            response = iot_client.create_thing(thingName=thingName)
        else:
            response = iot_client.create_thing(thingName=thingName,
                                               thingTypeName=thingTypeName)

        response = iot_client.attach_thing_principal( thingName=thingName,
                                                      principal=certificateArn)
            
        return 
    except Exception as e:
        print("ERROR Thing creation and attachment failed.")
        print(e)
        return None

def process_certificate(payload):
    client = boto3.client('iot')

    certificateText = base64.b64decode(eval(payload))

    # See if the certificate has already been registered.  If so, bail.
    certificateObj = x509.load_pem_x509_certificate(data=certificateText,
                                                    backend=default_backend())

    fingerprint = binascii.hexlify(certificateObj.fingerprint(hashes.SHA256())).decode('UTF-8')
    print("Fingerprint: " + fingerprint)

    if (get_certificate(fingerprint)):
        try:
            response = iot_client.describe_certificate(certificateId=fingerprint)
            print("Certificate already found. Returning certificateId in case this is recovering from a broken load")
        
            return response["certificateDescription"].get("certificateId")
        except:
            print("Certificate [" + fingerprint + "] not found in IoT Core. Importing.")

        
    try:
        response = iot_client.register_certificate_without_ca(certificatePem=certificateText.decode('ascii'),
                                                              status='ACTIVE')
        return response.get("certificateId")
    except BaseException as e:
        print("exception occurred: {}".format(e))

    return None

def process_thing_group(thingGroupName, thingName):
    try:
        thingGroupArn = get_thing_group(thingGroupName)
        thingArn = get_thing(thingName)
        
        iot_client.add_thing_to_thing_group(thingGroupName=thingGroupName,
                                            thingGroupArn=thingGroupArn,
                                            thingName=thingName,
                                            thingArn=thingArn,
                                            overrideDynamicGroups=False)
    except Exception as e:
        print(e)
        return None

def get_name_from_certificate(certificateId):
    response = iot_client.describe_certificate(certificateId=certificateId)
    certificateText = response["certificateDescription"].get("certificatePem")
    certificateObj = x509.load_pem_x509_certificate(data=certificateText.encode('ascii'), backend=default_backend())
    cn = certificateObj.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value
    # spaces are evil
    cn = "".join(cn.split())
    print("Common name to be Thing Name: [" + cn + "]")
    return cn

def process_sqs(config):
    certificate = config.get('certificate')
    policyName = config.get('policy_name')
    thingGroupName = config.get('thing_group_name')
    thingTypeName = config.get('thing_type_name')

    certificateId = process_certificate(certificate)
    
    if (certificateId is None):
        print("certificateId is None. Something bad happened. Exiting.")
        return None

    thingName = get_name_from_certificate(certificateId)

    process_thing(thingName, certificateId, thingTypeName)
    process_policy(policyName, certificateId)
    process_thing_group(thingGroupName, thingName)

def lambda_handler(event, context):
    if event.get('Records') is None:
        print("ERROR: Configuration incorrect: no event record on invoke")
        return
    
    for record in event['Records']:
        if record.get('eventSource') == 'aws:sqs':
            process_sqs(json.loads(record["body"]))

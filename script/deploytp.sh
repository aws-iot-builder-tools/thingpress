
# Copyright (C) 2021 Amazon.com, Inc. All Rights Reserved.
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
#! /bin/bash

echo Thingpress deploy script.
echo Arguments are shown below. If you do not want to define a parameter \(except
echo stack name\) then just use empty double quotes.
echo 1. name of CloudFormation stack to be created or updated 
echo 2. iot policy name
echo 3. iot thing group name
echo 4. iot thing type name
echo 5. s3 bucket name (globally unique)
echo 6. the AWS Region to deploy to. Example: us-east-1
echo "7. ARN of an IAM role that CloudFormation can assume. Example: arn:aws:iam::<account id>:role/<role name>"

if test $# != 7; then echo Insufficient arguments - Please read instructions above.; exit 1; fi

# validate stack name for compliance with s3 bucket naming rules
stackname=$1
for (( i=0; i<${#stackname}; i++ )); do
  letter="${stackname:$i:1}"
  if [[ $letter =~ ^[A-Z] ]]
  then
	  echo "ERROR: Stack name should not have uppercase letters - exiting..."
      exit  1
  elif [[ $letter == "." ]]; then
	  echo "ERROR: Stack name should not have '.'- exiting..."
      exit  1
  fi
done

P=$(pwd)/$(dirname $0)
cd ${P}/..
sam build --use-container

echo Build successful

sam package --s3-bucket $5 \
    --output-template-file ${P}/../packaged.yaml

echo Packaging successful

iot_policy="ParameterKey=IoTPolicy,ParameterValue=\"$2\""
iot_thing_group="ParameterKey=IoTThingGroup,ParameterValue=\"$3\""
iot_thing_type="ParameterKey=IoTThingType,ParameterValue=\"$4\""
s3bucket="ParameterKey=S3Bucket,ParameterValue=\"$5\""
region="ParameterKey=AWSRegion,ParameterValue=\"$6\""

cd ${P}/..

sam deploy \
    --template-file packaged.yaml \
    --capabilities CAPABILITY_NAMED_IAM \
    --stack-name $1 \
    --s3-bucket $5 \
    --region $6 \
    --role-arn $7 \
    --parameter-overrides "${iot_policy} ${iot_thing_group} ${iot_thing_type}"

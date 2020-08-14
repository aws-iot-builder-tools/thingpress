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
#! /bin/bash
echo Arguments are as follows. If you do not want to define the object \(except
echo stack name\) then just use empty double quotes.
echo 1. stack name
echo 2. iot policy name
echo 3. iot thing group name
echo 4. iot thing type name

if test $# != 4; then echo Please read instructions above.; exit 1; fi

iot_policy="ParameterKey=IoTPolicy,ParameterValue=\"$2\""
iot_thing_group="ParameterKey=IoTThingGroup,ParameterValue=\"$3\""
iot_thing_type="ParameterKey=IoTThingType,ParameterValue=\"$4\""

P=$(pwd)/$(dirname $0)
cd ${P}/..

sam deploy \
    --template-file packaged.yaml \
    --capabilities CAPABILITY_NAMED_IAM \
    --stack-name $1 \
    --parameter-overrides "${iot_policy} ${iot_thing_group} ${iot_thing_type}"

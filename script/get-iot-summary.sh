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

if test $# != 1  
then 
 	echo " "
 	echo Usage: $0 "<your region e.g us-east-1>"
    exit 1
else
	myregion=$1
fi

echo "IoT Summary"
echo "$(aws iam get-user | grep UserName) Region:$myregion" | sed 's/,//' | sed 's/        //'
echo "Number of things: $(aws iot list-things --region $myregion| grep thingArn | wc -l) "

echo "Number of thing types: $(aws iot list-thing-types --region $myregion| grep thingTypeArn | wc -l) "

echo "Number of thing groups: $(aws iot list-thing-groups --region $myregion| grep groupArn | wc -l) "

echo "Number of certificates: $(aws iot list-certificates --region $myregion| grep certificateArn | wc -l) "

echo "Number of active certificates: $(aws iot list-certificates --region $myregion| grep ACTIVE | wc -l) "

echo "Number of policies: $(aws iot list-policies --region $myregion| grep policyArn | wc -l) "

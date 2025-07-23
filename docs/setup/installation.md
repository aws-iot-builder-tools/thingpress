## Step 2: Building and installing the tool
# Prerequisites

- [Identify any need to increase limit quotas](aws-api-limits.md).
- Amazon Web Services account. If you don't have an account, refer to https://docs.aws.amazon.com/iot/latest/developerguide/setting-up.html.  The relevant sections are **Sign up for an AWS account** and **Create a user and grant permissions**.  
- Basic experience with Amazon CloudFormation 
- Linux workstation or Amazon Linux EC2 instance with:
  - Docker
  - Amazon Web Services Command Line Interface (CLI)
  - Amazon Web Services Serverless Application Model (SAM) CLI
  - Amazon Web Services IAM credentials with appropriate Role
    permissions and programmatic access for: 
        IAM, SQS, S3, Lambda, IoT, CloudFormation, CloudWatch



Before starting, you must identify the AWS IoT objects you will use at
scale.

- Required: AWS IoT Policy. This policy must be created in AWS IoT Core.
- Optional but highly recommended: AWS IoT Thing Type
- Optional but highly recommended: AWS IoT Thing Group


These steps assume you are building and installing the tool on a
GNU/Linux operating system such as a local workstation or EC2 instance
with the appropriate policy and/or IAM programmatic credential.

1. Clone the thingpress repository.

   ```bash
   git clone https://github.com/awslabs/thingpress thingpress
   ```
   
2. Install python module dependencies.
   
   ```bash
   pip install -r requirements.txt
   ```

3. Enter the script directory.
   
   ```bash
   cd thingpress/script
   ```
   
4. Invoke the Lambda function build script.  It has been known that
   VPN interrupts this process since it can interfere with Docker
   operation.
   
   ```bash
   ./build.sh
   ```
   
5. Create a private S3 bucket that will be used for deployment

   ```bash
   aws s3api create-bucket --acl private –-bucket <my_unique_s3_bucket>
   ```

6. Invoke the packaging process.  This will copy files to S3 and
   create a ```packaged.yaml`` file that evolves the template.yaml file to use S3
   URLs for deployment.

   ```bash
   ./package.sh <my_unique_s3_bucket>
   ```

7. Invoke the deploy script with a unique stack name and parameters
   for the IoT objects you wish to attach later. Note that during the
   deploy phase these objects are NOT cross-checked for validity.
   
   ```bash
   ./deploy.sh <stackname> <policyname> <thinggroupname> <thingtypename> <s3 bucket name> <aws region> <arn of IAM role> 
   ```

Tool installation is now complete.

# Thingpress Installation Guide

This guide covers the complete installation and setup process for Thingpress, including vendor-specific configurations.

## Prerequisites

- [Identify any need to increase limit quotas](aws-api-limits.md)
- Amazon Web Services account. If you don't have an account, refer to https://docs.aws.amazon.com/iot/latest/developerguide/setting-up.html. The relevant sections are **Sign up for an AWS account** and **Create a user and grant permissions**
- Basic experience with Amazon CloudFormation 
- Linux workstation or Amazon Linux EC2 instance with:
  - Docker
  - Amazon Web Services Command Line Interface (CLI)
  - Amazon Web Services Serverless Application Model (SAM) CLI
  - Amazon Web Services IAM credentials with appropriate Role permissions and programmatic access for: IAM, SQS, S3, Lambda, IoT, CloudFormation, CloudWatch

## Step 1: Prepare AWS IoT Objects

Before starting, you must identify the AWS IoT objects you will use at scale:

- **Required:** AWS IoT Policy. This policy must be created in AWS IoT Core
- **Optional but highly recommended:** AWS IoT Thing Type
- **Optional but highly recommended:** AWS IoT Thing Group

## Step 2: Build and Deploy Thingpress

These steps assume you are building and installing the tool on a GNU/Linux operating system such as a local workstation or EC2 instance with the appropriate policy and/or IAM programmatic credential.

1. **Clone the thingpress repository**
   ```bash
   git clone https://github.com/awslabs/thingpress thingpress
   cd thingpress
   ```
   
2. **Install python module dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Build Lambda functions**
   ```bash
   cd scripts
   ./build.sh
   ```
   
   > **Note:** VPN may interfere with Docker operation during this process.

4. **Create deployment S3 bucket**
   ```bash
   aws s3api create-bucket --acl private --bucket <my_unique_s3_bucket>
   ```

5. **Package the application**
   ```bash
   ./package.sh <my_unique_s3_bucket>
   ```

## Step 3: Vendor-Specific Configuration

Choose your hardware vendor and follow the vendor-specific deployment instructions:

### Select Your Vendor:

- **[Espressif Systems (ESP32-S3)](../vendors/espressif.md#deployment)** - For ESP32-S3 devices with pre-provisioned certificates
- **[Infineon Technologies (Optiga Trust M Express)](../vendors/infineon.md#deployment)** - For Optiga Trust M Express security chips
- **[Microchip Technology (Trust&Go ATECC608B)](../vendors/microchip.md#deployment)** - For Trust&Go ATECC608B with TLS
- **[Generated Certificates](../vendors/generated.md#deployment)** - For programmatically generated certificates or migration scenarios

Each vendor guide will walk you through:
- Vendor-specific SAM deployment parameters
- How to obtain certificate manifests from the vendor
- Deployment command examples
- Manifest upload process

## Step 4: Verify Installation

After completing your vendor-specific deployment, return here to verify your installation:

1. **Check CloudFormation stack status**
   ```bash
   aws cloudformation describe-stacks --stack-name <your-stack-name>
   ```

2. **Verify S3 buckets were created**
   ```bash
   aws s3 ls | grep <your-stack-name>
   ```

3. **Test with a small manifest file** (follow your vendor's upload process)

4. **Monitor processing in CloudWatch Logs**
   - Navigate to CloudWatch → Log groups
   - Look for log groups with your stack name prefix
   - Monitor certificate processing progress

## Step 5: Production Readiness

Before processing large certificate batches:

1. **Review [AWS API limits](aws-api-limits.md)** and request increases if needed
2. **Test with small batches** (100-1000 certificates) first
3. **Monitor performance** and adjust throttling if necessary
4. **Verify AWS IoT objects** are created correctly

## Troubleshooting

If you encounter issues:
- Check CloudWatch Logs for error messages
- Verify AWS IAM permissions are correctly configured
- Ensure AWS IoT objects (Policy, Thing Type, Thing Group) exist
- Refer to vendor-specific troubleshooting in the vendor documentation

## Next Steps

- **Upload certificates:** Follow your vendor's manifest upload process
- **Monitor processing:** Use CloudWatch to track certificate import progress
- **Scale up:** Process larger certificate batches once testing is complete

---

**Need help?** Refer to the vendor-specific documentation linked above or check the troubleshooting section.

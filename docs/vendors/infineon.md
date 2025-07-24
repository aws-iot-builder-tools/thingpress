# Thingpress for Infineon Technologies

This guide covers Thingpress setup and usage for **Infineon Optiga Trust M Express** security chips with pre-provisioned X.509 certificates.

## Overview

Infineon Optiga Trust M Express security chips come with pre-provisioned X.509 certificates in secure certificate bundles. Thingpress processes these certificate bundles and imports them into AWS IoT Core for device authentication.

## Prerequisites

Complete the [main installation guide](../setup/installation.md) through **Step 2** before proceeding with Infineon-specific configuration.

## Deployment

### SAM Deployment Parameters

Deploy Thingpress with Infineon-specific parameters:

```bash
sam deploy \
  --stack-name thingpress-infineon \
  --parameter-overrides \
    PolicyName=<your-iot-policy-name> \
    ThingGroupName=<your-thing-group-name> \
    ThingTypeName=<your-thing-type-name> \
    S3BucketName=<your-deployment-bucket> \
    Region=<your-aws-region> \
    RoleArn=<your-iam-role-arn> \
    CertificateType=<E0E0|E0E1|E0E2>
```

### Certificate Bundle Types

Infineon provides different certificate bundle types:

- **E0E0:** Basic certificate bundle
- **E0E1:** Enhanced certificate bundle with additional metadata
- **E0E2:** Advanced certificate bundle with extended features

Choose the appropriate type based on your Optiga Trust M Express configuration.

### Expected AWS Resources

After deployment, to view all created resources:

1. **Navigate to CloudFormation** in the AWS Console
2. **Select your stack** (e.g., `thingpress-infineon`)
3. **Click the "Resources" tab** to see all created AWS resources
4. **Review resource status** and physical IDs for troubleshooting

## Obtaining Certificate Manifests

### From Infineon Technologies

1. **Contact Infineon** through their official channels or authorized distributors
2. **Request certificate bundles** for your Optiga Trust M Express devices
3. **Specify bundle type** (E0E0, E0E1, or E0E2) based on your requirements
4. **Obtain manifest files** in the appropriate format for your bundle type

### Manifest Format

Infineon provides certificate bundles in XML format:
- **Archive format:** XML manifest files
- **Contents:** Certificate bundles with device-specific certificates
- **Metadata:** Device identifiers and certificate chain information

## Certificate Upload Process

### Step 1: Access S3 Bucket

1. **Login to AWS Console**
2. **Navigate to S3** via the Services menu
3. **Locate bucket:** `thingpress-infineon-infineon` (or your custom stack name + "-infineon")

### Step 2: Upload Files

1. **Upload the XML manifest file** to the S3 bucket
   - Use drag-and-drop or the Upload button
   - File upload triggers automatic processing
   - Processing begins immediately upon successful upload

### Step 3: Monitor Processing

1. **CloudWatch Logs:** Monitor processing progress
   - Navigate to CloudWatch → Log groups
   - Look for log groups with your stack name prefix
   - Check manifest processing and certificate extraction status

2. **AWS IoT Core:** Verify certificate registration
   - Navigate to AWS IoT Core → Manage → Things
   - Confirm new Things are created with proper names
   - Verify certificates are attached and active

## Configuration Options

### Bundle Type Selection

Configure the appropriate certificate bundle type during deployment:

```bash
# For E0E0 bundles
CertificateType=E0E0

# For E0E1 bundles  
CertificateType=E0E1

# For E0E2 bundles
CertificateType=E0E2
```

### Thing Naming

- **Default:** Thing names derived from certificate Common Name (CN)
- **Format:** Extracted from certificate subject field
- **Uniqueness:** Ensured by certificate CN uniqueness

### Attachments

Each imported certificate will have the following attachments:
- **Certificate:** X.509 certificate registered in AWS IoT
- **Thing:** IoT Thing created with CN-based name
- **Policy:** Attached policy specified in deployment parameters
- **Thing Type:** Attached Thing Type (if specified)
- **Thing Group:** Attached Thing Group (if specified)

## Performance Considerations

### Manifest Processing

- **XML parsing:** Automatic manifest parsing and validation
- **Batch processing:** Certificates processed in optimal batches
- **Processing rate:** Approximately 100,000 certificates per hour
- **Throttling:** Automatic throttling prevents AWS API limits

### Scaling

For large deployments:
1. **Split large manifests** if they exceed processing limits
2. **Monitor CloudWatch metrics** for processing rates
3. **Check AWS service limits** and request increases if necessary

## Troubleshooting

### Common Issues

**Upload fails:**
- Verify S3 bucket permissions
- Check XML manifest format and validity
- Ensure file size is within S3 limits

**Manifest processing fails:**
- Verify XML manifest format and validity
- Check certificate bundle type matches deployment configuration (E0E0, E0E1, E0E2)
- Ensure manifest file is not corrupted

**Processing errors:**
- Check CloudWatch Logs for detailed error messages
- Verify AWS IoT objects (Policy, Thing Type, Thing Group) exist
- Confirm IAM permissions are correctly configured
- Validate certificate bundle type selection

**Certificate registration fails:**
- Verify certificate format and validity within manifest
- Check for duplicate certificates
- Ensure certificate CN values are unique

### Monitoring

**CloudWatch Metrics:**
- Lambda function invocations and errors
- Manifest processing success/failure rates
- SQS queue depth and processing rates
- S3 upload events and failures

**AWS IoT Core:**
- Certificate registration status
- Thing creation and attachment status
- Policy attachment verification

## Next Steps

After successful certificate import:

1. **Verify device connectivity** - Test Optiga Trust M Express device connections
2. **Monitor device behavior** - Use CloudWatch and AWS IoT Device Management
3. **Scale operations** - Process additional certificate manifests as needed

Return to the [main installation guide](../setup/installation.md#step-4-verify-installation) to complete the verification process.

---

**Need help?** Check the troubleshooting section above or refer to the main installation guide for general Thingpress support.

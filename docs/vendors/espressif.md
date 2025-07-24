# Thingpress for Espressif Systems

This guide covers Thingpress setup and usage for **Espressif ESP32-S3** devices with pre-provisioned X.509 certificates.

## Overview

Espressif ESP32-S3 devices can be manufactured with pre-provisioned X.509 certificates stored in secure elements. Thingpress imports these certificates into AWS IoT Core and creates the necessary IoT Things for device authentication.

## Prerequisites

Complete the [main installation guide](../setup/installation.md) through **Step 2** before proceeding with Espressif-specific configuration.

## Deployment

### SAM Deployment Parameters

Deploy Thingpress with Espressif-specific parameters:

```bash
sam deploy \
  --stack-name thingpress-espressif \
  --parameter-overrides \
    PolicyName=<your-iot-policy-name> \
    ThingGroupName=<your-thing-group-name> \
    ThingTypeName=<your-thing-type-name> \
    S3BucketName=<your-deployment-bucket> \
    Region=<your-aws-region> \
    RoleArn=<your-iam-role-arn>
```

### Expected AWS Resources

After deployment, to view all created resources:

1. **Navigate to CloudFormation** in the AWS Console
2. **Select your stack** (e.g., `thingpress-espressif`)
3. **Click the "Resources" tab** to see all created AWS resources
4. **Review resource status** and physical IDs for troubleshooting

## Obtaining Certificate Manifests

### From Espressif Systems

1. **Contact Espressif** through their official channels for pre-provisioned certificate manifests
2. **Request format:** CSV manifest file containing certificate data for your ESP32-S3 devices
3. **Verification certificate:** Obtain the verification certificate for manifest validation

### Manifest Format

Espressif provides manifests in CSV format with the following required columns:
- **MAC:** Device MAC address (used as AWS IoT Thing name)
- **cert:** X.509 certificate data (PEM format)
- Additional columns may be present but are not processed

## Certificate Upload Process

### Step 1: Access S3 Bucket

1. **Login to AWS Console**
2. **Navigate to S3** via the Services menu
3. **Locate bucket:** `thingpress-espressif-esp32s3` (or your custom stack name + "-esp32s3")

### Step 2: Upload Manifest

1. **Upload the CSV manifest file** to the S3 bucket
   - Use drag-and-drop or the Upload button
   - File upload triggers automatic processing
2. **Processing begins immediately** upon successful upload

### Step 3: Monitor Processing

1. **CloudWatch Logs:** Monitor processing progress
   - Navigate to CloudWatch → Log groups
   - Look for log groups with your stack name prefix
   - Check for processing status and any errors

2. **AWS IoT Core:** Verify certificate registration
   - Navigate to AWS IoT Core → Manage → Things
   - Confirm new Things are created with proper names (based on certificate CN)
   - Verify certificates are attached and active

## Configuration Options

### Thing Naming

- **Espressif-specific:** Thing names derived from **MAC address field** in CSV manifest
- **Format:** Uses the 'MAC' column value from the Espressif CSV file
- **Uniqueness:** Ensured by MAC address uniqueness per device
- **Note:** Unlike other vendors, Espressif does not use certificate CN for Thing names

### Attachments

Each imported certificate will have the following attachments:
- **Certificate:** X.509 certificate registered in AWS IoT
- **Thing:** IoT Thing created with CN-based name
- **Policy:** Attached policy specified in deployment parameters
- **Thing Type:** Attached Thing Type (if specified)
- **Thing Group:** Attached Thing Group (if specified)

## Performance Considerations

### Batch Processing

- **Optimal batch size:** 1000 certificates per manifest file
- **Processing rate:** Approximately 100,000 certificates per hour
- **Throttling:** Automatic throttling prevents AWS API limits

### Scaling

For large deployments:
1. **Split large manifests** into smaller batches if needed
2. **Monitor CloudWatch metrics** for processing rates
3. **Check AWS service limits** and request increases if necessary

## Troubleshooting

### Common Issues

**Upload fails:**
- Verify S3 bucket permissions
- Check file format matches expected CSV structure
- Ensure file size is within S3 limits

**Processing errors:**
- Check CloudWatch Logs for detailed error messages
- Verify AWS IoT objects (Policy, Thing Type, Thing Group) exist
- Confirm IAM permissions are correctly configured

**Certificate registration fails:**
- Verify certificate format and validity
- Check for duplicate certificates
- Ensure certificate CN values are unique

### Monitoring

**CloudWatch Metrics:**
- Lambda function invocations and errors
- SQS queue depth and processing rates
- S3 upload events and failures

**AWS IoT Core:**
- Certificate registration status
- Thing creation and attachment status
- Policy attachment verification

## Next Steps

After successful certificate import:

1. **Verify device connectivity** - Test device connections to AWS IoT Core
2. **Monitor device behavior** - Use CloudWatch and AWS IoT Device Management
3. **Scale operations** - Process additional certificate batches as needed

Return to the [main installation guide](../setup/installation.md#step-4-verify-installation) to complete the verification process.

---

**Need help?** Check the troubleshooting section above or refer to the main installation guide for general Thingpress support.


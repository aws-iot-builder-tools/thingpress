# Thingpress for Microchip Technology

This guide covers Thingpress setup and usage for **Microchip Trust&Go ATECC608B with TLS** security chips with pre-provisioned X.509 certificates.

## Overview

Microchip Trust&Go ATECC608B devices come with pre-provisioned X.509 certificates secured with JWS (JSON Web Signature) tokens. Thingpress processes these JWS-protected certificate manifests and imports them into AWS IoT Core for device authentication.

## Prerequisites

Complete the [main installation guide](../setup/installation.md) through **Step 2** before proceeding with Microchip-specific configuration.

## Deployment

### SAM Deployment Parameters

Deploy Thingpress with Microchip-specific parameters:

```bash
sam deploy \
  --stack-name thingpress-microchip \
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
2. **Select your stack** (e.g., `thingpress-microchip`)
3. **Click the "Resources" tab** to see all created AWS resources
4. **Review resource status** and physical IDs for troubleshooting

## Obtaining Certificate Manifests

### From Microchip Technology

1. **Access MicrochipDirect** - Visit the official Microchip Direct portal
2. **Request certificate manifests** for your Trust&Go ATECC608B devices
3. **Download JWS-protected manifest** - Certificate data secured with JSON Web Signature
4. **Obtain verification certificate** - Required for JWS token validation

### Manifest Format

Microchip provides certificate manifests in JWS-protected format:
- **Format:** JSON Web Signature (JWS) tokens
- **Contents:** Certificate data with device identifiers
- **Security:** Cryptographically signed by Microchip
- **Verification:** Requires Microchip verification certificate

## Certificate Upload Process

### Step 1: Baseline IoT Summary (Optional)

Before processing, optionally capture current IoT state:

```bash
scripts/get-iot-summary.sh <aws-region>
```

This helps verify the import results later.

### Step 2: Access S3 Bucket

1. **Login to AWS Console**
2. **Navigate to S3** via the Services menu
3. **Locate bucket:** `thingpress-microchip-microchip` (or your custom stack name + "-microchip")

### Step 3: Upload Files

1. **Upload verification certificate first**
   - Upload the Microchip verification certificate file (without .json extension)
   - This validates the JWS token authenticity

2. **Upload the JWS manifest file** to the S3 bucket
   - Use drag-and-drop or the Upload button
   - File upload triggers automatic JWS processing
   - Processing begins immediately upon successful upload

### Step 4: Monitor Processing

1. **CloudWatch Logs:** Monitor processing progress
   - Navigate to CloudWatch → Log groups
   - Look for log groups with your stack name prefix
   - Check JWS token validation and certificate extraction status

2. **AWS IoT Core:** Verify certificate registration
   - Navigate to AWS IoT Core → Manage → Things
   - Confirm new Things are created with proper names
   - Verify certificates are attached and active

### Step 5: Verify Results (Optional)

Compare before and after IoT summaries:

```bash
scripts/get-iot-summary.sh <aws-region>
```

Verify the correct number of certificates and Things were added.

## Configuration Options

### JWS Token Processing

- **Automatic validation:** JWS tokens validated against Microchip verification certificate
- **Certificate extraction:** X.509 certificates extracted from validated tokens
- **Security verification:** Cryptographic signature validation ensures authenticity

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

### JWS Processing

- **Token validation:** Cryptographic verification of JWS signatures
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
- Check JWS manifest format and validity
- Ensure file size is within S3 limits

**JWS validation fails:**
- Ensure verification certificate is uploaded first
- Check verification certificate format (no .json extension)
- Verify JWS token signature integrity
- Confirm manifest is from authentic Microchip source

**Processing errors:**
- Check CloudWatch Logs for detailed error messages
- Verify AWS IoT objects (Policy, Thing Type, Thing Group) exist
- Confirm IAM permissions are correctly configured
- Validate JWS token structure and content

**Certificate registration fails:**
- Verify certificate format and validity within JWS tokens
- Check for duplicate certificates
- Ensure certificate CN values are unique

### Monitoring

**CloudWatch Metrics:**
- Lambda function invocations and errors
- JWS validation success/failure rates
- SQS queue depth and processing rates
- S3 upload events and failures

**AWS IoT Core:**
- Certificate registration status
- Thing creation and attachment status
- Policy attachment verification

## Security Considerations

### JWS Token Security

- **Cryptographic validation:** All JWS tokens verified against Microchip certificates
- **Tamper detection:** Invalid or modified tokens rejected
- **Authentic source:** Only Microchip-signed manifests accepted

### Best Practices

- **Secure storage:** Store verification certificates securely
- **Access control:** Limit S3 bucket access to authorized users
- **Monitoring:** Monitor for failed validation attempts

## Next Steps

After successful certificate import:

1. **Verify device connectivity** - Test Trust&Go ATECC608B device connections
2. **Monitor device behavior** - Use CloudWatch and AWS IoT Device Management
3. **Scale operations** - Process additional certificate manifests as needed

Return to the [main installation guide](../setup/installation.md#step-4-verify-installation) to complete the verification process.

---

**Need help?** Check the troubleshooting section above or refer to the main installation guide for general Thingpress support.

# Thingpress for Generated Certificates

This guide covers Thingpress setup and usage for **arbitrary certificate imports** from any source that can produce properly formatted certificate files.

## Overview

The Generated Certificates Provider processes certificate files containing X.509 certificates in a standardized format. This provider enables you to import certificates from any source - whether generated programmatically, exported from other IoT platforms, or created by custom tools - as long as they match the expected input format.

## Prerequisites

Complete the [main installation guide](../setup/installation.md) through **Step 2** before proceeding with Generated Certificates configuration.

## Use Cases

### Certificate Import Sources
- **Migration from other IoT platforms** (Azure IoT Hub, Google Cloud IoT, etc.)
- **Custom PKI systems** and enterprise certificate authorities
- **Legacy IoT deployments** with existing certificate inventories
- **Development and testing** environments with generated certificates
- **Third-party certificate management** systems

### Common Scenarios
- **Platform migration** - Moving from Azure IoT Hub to AWS IoT Core
- **System consolidation** - Importing certificates from multiple sources
- **Certificate lifecycle management** - Bulk import of renewed certificates
- **Development workflows** - Testing with programmatically generated certificates

## Deployment

### SAM Deployment Parameters

Change directory to the Thingpress project root directory.
```bash
$ cd thingpress # navigate to project root
```

Modify TOML file parameters.
```bash
$ vi configs/sam-integration-full.toml
```

Edit the following properties. The property value is the object name (not ARN). Set the property value to `\"\"` if you do not wish to configure those properties.
- IoTPolicy
- IoTThingGroup
- IoTThingType

Deploy Thingpress.

```bash
$ sam deploy \
   --stack-name thingpress-espressif \
   --region REGION \
   --resolve-s3 \
   --config-file CONFIG \
   --capabilities CAPABILITY_NAMED_IAM \
   --no-confirm-changeset \
   --no-fail-on-empty-changeset
```

Where:
- REGION is your target deployment AWS region.
  - example: us-east-1
- CONFIG is the toml config file. Toml config is in a SAM-expected format.
  - example: configs/sam-integration-full.toml

For example:
```bash
$ sam deploy \
   --stack-name thingpress-espressif \
   --region us-east-1 \
   --resolve-s3 \
   --config-file configs/sam-integration-full.toml \
   --capabilities CAPABILITY_NAMED_IAM \
   --no-confirm-changeset \
   --no-fail-on-empty-changeset
```

## Multiple Policies and Thing Groups

Thingpress supports attaching multiple policies, thing groups, and thing types to each certificate/thing. This enables hierarchical organization and layered access control for enterprise IoT deployments.

### Using Multiple Values

Use comma-delimited lists in your deployment parameters:

```bash
$ sam deploy \
   --stack-name thingpress-generated \
   --region us-east-1 \
   --parameter-overrides \
     IoTPolicies=base-connectivity,sensor-telemetry,admin-access \
     IoTThingGroups=dept-engineering,location-seattle,product-sensor \
     IoTThingType=custom-device \
   --capabilities CAPABILITY_NAMED_IAM
```

Or in your TOML configuration file:

```toml
parameter_overrides = "IoTPolicies=\"base-policy,sensor-policy\" IoTThingGroups=\"dept-eng,location-us-west\""
```

### Common Use Cases

**Layered Access Control:**
```bash
IoTPolicies=base-connectivity,role-sensor,location-restricted
```
- Base policy: MQTT connectivity
- Role policy: Sensor-specific permissions  
- Location policy: Regional restrictions

**Organizational Hierarchy:**
```bash
IoTThingGroups=company-acme,dept-manufacturing,location-seattle,line-assembly-1
```
- Organize devices by company → department → location → production line

**Legacy Single-Value (Still Supported):**
```bash
IoTPolicy=my-policy
IoTThingGroup=my-group
```

For detailed examples, best practices, and troubleshooting, see the [Multiple Attachments Guide](../MULTI_ATTACHMENT_GUIDE.md).

## Certificate File Format Requirements

### Input Format Specification

The Generated provider expects certificate files with the following format:

**File Format:**
- **Text files** with `.txt` extension (other extensions supported)
- **One certificate per line** in base64 format
- **UTF-8 encoding** required
- **Unix line endings** preferred (LF)

**Certificate Format:**
```
<base64-encoded-certificate-1>
<base64-encoded-certificate-2>
<base64-encoded-certificate-3>
...
```

**Example:**
```
LS0tLS1CRUdJTiBDRVJUSUZJQ0FURS0tLS0tCk1JSUNpakNDQWkrZ0F3SUJBZ0lVQm...
LS0tLS1CRUdJTiBDRVJUSUZJQ0FURS0tLS0tCk1JSUNpakNDQWkrZ0F3SUJBZ0lVQm...
LS0tLS1CRUdJTiBDRVJUSUZJQ0FURS0tLS0tCk1JSUNpakNDQWkrZ0F3SUJBZ0lVQm...
```

### Certificate Requirements

**X.509 Certificate Standards:**
- **Valid X.509 certificates** in PEM format (before base64 encoding)
- **Unique Common Names (CN)** for each certificate (used as Thing names)
- **Non-expired certificates** recommended

**Thing Naming:**
- **Thing names derived from certificate Common Name (CN)**
- **CN must be unique** across all certificates in the batch
- **CN format should follow** AWS IoT Thing naming conventions

## Creating Compatible Certificate Files

### Using the Certificate Generator (Example)

The included certificate generator demonstrates the correct format:

```bash
python src/certificate_generator/generate_certificates.py \
  --count 100 \
  --output-dir ./output \
  --key-type ec \
  --ec-curve secp256r1
```

**Generated files will be in the correct format** for the Generated provider.

### From Azure IoT Hub Migration

For Azure IoT Hub migrations, use the export script:

```bash
python scripts/export_azure_certificates.py \
  --connection-string "HostName=yourhub.azure-devices.net;..." \
  --output-dir ./azure_certs \
  --format base64
```

**The export script produces files** in the correct format for import.

### From Custom Sources

To create compatible files from your own certificate sources:

1. **Extract X.509 certificates** in PEM format
2. **Remove PEM headers/footers** (-----BEGIN CERTIFICATE-----, etc.)
3. **Base64 encode each certificate** (single line, no line breaks)
4. **Place one certificate per line** in a text file
5. **Ensure unique CN values** for each certificate

**Example conversion:**
```bash
# From PEM file to base64 line
openssl x509 -in certificate.pem -outform DER | base64 -w 0
```

## Certificate Upload Process

### Step 1: Access S3 Bucket

1. **Login to AWS Console**
2. **Navigate to S3** via the Services menu
3. **Locate bucket:** Find your stack name with "-generated" suffix

### Step 2: Upload Certificate Files

1. **Upload certificate files** to the S3 bucket
   - Use drag-and-drop or the Upload button
   - Support for `.txt`, `.csv`, and other text file extensions
   - Multiple files can be uploaded simultaneously

2. **Processing begins immediately** upon successful upload

### Step 3: Monitor Processing

1. **CloudWatch Logs:** Monitor processing progress
   - Navigate to CloudWatch → Log groups
   - Look for log groups with your stack name prefix
   - Check certificate parsing and processing status

2. **AWS IoT Core:** Verify certificate registration
   - Navigate to AWS IoT Core → Manage → Things
   - Confirm new Things are created with CN-based names
   - Verify certificates are attached and active

## Configuration Options

### File Processing

- **Multiple file formats** supported (txt, csv, dat, etc.)
- **Batch processing** of certificates within files
- **Error handling** for malformed certificates
- **Progress tracking** via CloudWatch Logs

### Thing Naming

- **Thing names derived from certificate Common Name (CN)**
- **Format:** Extracted from certificate subject field
- **Uniqueness:** Must be unique across all certificates
- **Validation:** Invalid CN values will cause processing errors

### Attachments

Each imported certificate will have the following attachments:
- **Certificate:** X.509 certificate registered in AWS IoT
- **Thing:** IoT Thing created with CN-based name
- **Policy:** Attached policy specified in deployment parameters
- **Thing Type:** Attached Thing Type (if specified)
- **Thing Group:** Attached Thing Group (if specified)

## Performance Considerations

### Batch Processing

- **File processing:** Automatic parsing of certificate files
- **Batch optimization:** Certificates processed in optimal batches
- **Processing rate:** Approximately 100,000 certificates per hour
- **Throttling:** Automatic throttling prevents AWS API limits

### Scaling

For large imports:
1. **Split large files** into smaller batches (10,000-50,000 certificates per file)
2. **Monitor CloudWatch metrics** for processing rates
3. **Check AWS service limits** and request increases if necessary
4. **Use parallel uploads** for multiple certificate files

## Troubleshooting

### Common Issues

**File format errors:**
- Verify certificates are base64 encoded (single line per certificate)
- Check for proper UTF-8 encoding
- Ensure no extra whitespace or special characters

**Certificate parsing fails:**
- Verify certificates are valid X.509 format
- Check that base64 encoding is correct
- Ensure certificates are not corrupted

**Thing creation fails:**
- Verify certificate CN values are unique
- Check that CN follows AWS IoT Thing naming rules
- Ensure certificates are not expired

**Processing errors:**
- Check CloudWatch Logs for detailed error messages
- Verify AWS IoT objects (Policy, Thing Type, Thing Group) exist
- Confirm IAM permissions are correctly configured

### Monitoring

**CloudWatch Metrics:**
- Lambda function invocations and errors
- File processing success/failure rates
- Certificate parsing statistics
- SQS queue depth and processing rates

**AWS IoT Core:**
- Certificate registration status
- Thing creation and attachment status
- Policy attachment verification

## Migration Best Practices

### Pre-Migration Planning

1. **Inventory source certificates** and validate format compatibility
2. **Plan Thing naming strategy** based on certificate CN values
3. **Test with small batches** (100-1000 certificates) first
4. **Prepare rollback procedures** if needed

### During Migration

1. **Monitor processing progress** via CloudWatch
2. **Validate certificate imports** in AWS IoT Core
3. **Handle errors promptly** to avoid data loss
4. **Track migration status** using processing logs

### Post-Migration

1. **Verify device connectivity** to AWS IoT Core
2. **Update device configurations** with new AWS IoT endpoints
3. **Monitor device behavior** and performance
4. **Decommission source systems** after validation

## Next Steps

After successful certificate import:

1. **Verify device connectivity** - Test device connections to AWS IoT Core
2. **Update device configurations** - Point devices to AWS IoT endpoints
3. **Monitor import success** - Use CloudWatch and AWS IoT Device Management
4. **Scale operations** - Process additional certificate batches as needed

Return to the [main installation guide](../setup/installation.md#step-4-verify-installation) to complete the verification process.

---

**Need help?** Check the troubleshooting section above or refer to the main installation guide for general Thingpress support.

```bash
sam deploy --template-file templates/provider_generated.yaml \
  --stack-name thingpress-provider-generated \
  --parameter-overrides \
    TargetQueueUrl=<your-bulk-importer-queue-url> \
    S3BucketName=<your-s3-bucket-name> \
    S3NotificationPrefix=certificates/
```

Replace the placeholder values with your actual configuration.

### 3. Upload Certificate Files

Upload the generated certificate files to the S3 bucket with the specified prefix:

```bash
aws s3 cp output/certificates_*.txt s3://<your-s3-bucket-name>/certificates/
```

## How It Works

1. When a certificate file is uploaded to the S3 bucket with the specified prefix, an S3 event notification is sent to the SQS queue.
2. The Lambda function processes the SQS messages, retrieves the certificate files from S3, and processes each certificate.
3. For each certificate:
   - The Common Name (CN) is extracted from the certificate to use as the Thing name
   - The certificate and Thing name are forwarded to the bulk importer queue
4. The bulk importer processes the certificates and creates the corresponding AWS IoT resources.

## Certificate Format

The certificate files should contain one base64-encoded certificate per line. Each certificate should include its full chain (end-entity certificate + intermediate CA + root CA).

This is the default output format of the `generate_certificates.py` script.

## Troubleshooting

### Common Issues

1. **Certificate Processing Failures**:
   - Check the Lambda function logs in CloudWatch Logs
   - Verify that the certificates are properly base64-encoded
   - Ensure the certificates include a valid Common Name (CN)

2. **S3 Event Notification Issues**:
   - Verify that the S3 bucket notification configuration is correct
   - Check that the uploaded files have the correct prefix

3. **Permission Issues**:
   - Ensure the Lambda function has the necessary permissions to read from S3 and send messages to SQS

### Monitoring

Monitor the following resources:

- Lambda function execution logs in CloudWatch Logs
- SQS queue metrics (ApproximateNumberOfMessages, ApproximateNumberOfMessagesNotVisible)
- Dead Letter Queue (DLQ) for failed processing

## Advanced Configuration

### Custom Thing Names

By default, the provider uses the Common Name (CN) from the certificate as the Thing name. If you need custom Thing names, you can modify the `extract_common_name` function in the Lambda code.

### Batch Processing

The Lambda function processes certificates in batches. You can adjust the batch size by modifying the `BatchSize` parameter in the CloudFormation template.

### Error Handling

Failed certificate processing attempts are sent to a Dead Letter Queue (DLQ) after three retries. You can monitor this queue to identify and resolve issues.

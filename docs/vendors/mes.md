# Thingpress for MES Two-Phase Provisioning

This guide covers Thingpress setup and usage for **MES (Manufacturing Execution System) two-phase provisioning** workflows where certificates are registered separately from device activation.

## Overview

The MES Provider implements a two-phase provisioning workflow designed for manufacturing environments where certificate registration and device activation occur at different stages of the production process. This approach enables secure certificate pre-registration during manufacturing (Phase 1) followed by device activation during final assembly or deployment (Phase 2).

### Two-Phase Workflow

**Phase 1 - Certificate Registration (JWO/Manufacturing):**
- Certificates registered as INACTIVE in AWS IoT Core
- Thing creation deferred (no IoT Things created yet)
- Certificates secured but not yet operational
- Typically performed during chip programming or initial manufacturing

**Phase 2 - Device Activation (MES/Final Assembly):**
- Certificates activated (INACTIVE → ACTIVE)
- IoT Things created with device identifiers and attributes
- Certificates attached to Things with policies and thing groups
- Device ready for production deployment

## Prerequisites

Complete the [main installation guide](../setup/installation.md) through **Step 2** before proceeding with MES-specific configuration.

## Use Cases

### Manufacturing Workflows
- **Chip programming stations** - Register certificates during secure element programming
- **Final assembly lines** - Activate devices with manufacturing data
- **Quality control gates** - Separate certificate registration from device activation
- **Multi-stage production** - Decouple security provisioning from device configuration

### Common Scenarios
- **Contract manufacturing** - Chip vendor registers certificates, OEM activates devices
- **Secure supply chain** - Certificates registered at secure facility, devices activated at assembly plant
- **Phased deployment** - Pre-register certificates, activate devices as needed
- **Manufacturing traceability** - Link certificates to manufacturing execution data

## Deployment

### SAM Deployment Parameters

Change directory to the Thingpress project root directory.
```bash
$ cd thingpress # navigate to project root
```

Modify TOML file parameters for two-phase provisioning.
```bash
$ vi configs/sam-integration-full.toml
```

Edit the following properties for Phase 1 (certificate registration):
- IoTCertActive=FALSE (registers certificates as INACTIVE)
- IoTThingDeferred=TRUE (defers Thing creation to Phase 2)
- IoTCertFormat (certificate format: PEM, DER, or base64)

Edit the following properties for Phase 2 (device activation):
- IoTPolicy (or IoTPolicies for multiple policies)
- IoTThingGroup (or IoTThingGroups for multiple groups)
- IoTThingType

Deploy Thingpress.

```bash
$ sam deploy \
   --stack-name thingpress-mes \
   --region REGION \
   --resolve-s3 \
   --config-file CONFIG \
   --capabilities CAPABILITY_NAMED_IAM \
   --no-confirm-changeset \
   --no-fail-on-empty-changeset
```

Where:
- REGION is your target deployment AWS region.
  - example: us-west-2
- CONFIG is the toml config file. Toml config is in a SAM-expected format.
  - example: configs/sam-integration-full.toml

For example:
```bash
$ sam deploy \
   --stack-name thingpress-mes \
   --region us-west-2 \
   --resolve-s3 \
   --config-file configs/sam-integration-full.toml \
   --capabilities CAPABILITY_NAMED_IAM \
   --no-confirm-changeset \
   --no-fail-on-empty-changeset
```

### Expected AWS Resources

After deployment, to view all created resources:

1. **Navigate to CloudFormation** in the AWS Console
2. **Select your stack** (e.g., `thingpress-mes`)
3. **Click the "Resources" tab** to see all created AWS resources
4. **Key resources include:**
   - S3 buckets for Phase 1 (vendor certificates) and Phase 2 (device-infos)
   - Lambda functions for certificate processing and device activation
   - SQS queues for message processing
   - IAM roles and policies

## Multiple Policies and Thing Groups

Thingpress supports attaching multiple policies, thing groups, and thing types to each certificate/thing. This enables hierarchical organization and layered access control for enterprise IoT deployments.

### Using Multiple Values

Use comma-delimited lists in your deployment parameters:

```bash
$ sam deploy \
   --stack-name thingpress-mes \
   --region us-west-2 \
   --parameter-overrides \
     IoTPolicies=base-connectivity,sensor-telemetry,manufacturing-data \
     IoTThingGroups=dept-manufacturing,location-plant-a,product-sensor \
     IoTThingType=production-device \
   --capabilities CAPABILITY_NAMED_IAM
```

Or in your TOML configuration file:

```toml
parameter_overrides = "IoTPolicies=\"base-policy,sensor-policy\" IoTThingGroups=\"dept-mfg,location-us-west\""
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
IoTThingGroups=company-acme,dept-manufacturing,location-plant-a,line-assembly-1
```
- Organize devices by company → department → location → production line

**Legacy Single-Value (Still Supported):**
```bash
IoTPolicy=my-policy
IoTThingGroup=my-group
```

For detailed examples, best practices, and troubleshooting, see the [Multiple Attachments Guide](../MULTI_ATTACHMENT_GUIDE.md).

## Device-Infos File Format Requirements

### Phase 2 Input Format Specification

The MES provider expects device-infos files in JSON format for Phase 2 activation:

**File Format:**
- **JSON files** with `.json` extension
- **UTF-8 encoding** required
- **Structured format** with batch metadata and device array

**JSON Structure:**
```json
{
  "batch_id": "batch-identifier",
  "devices": [
    {
      "certFingerprint": "64-character-hex-fingerprint",
      "deviceId": "unique-device-identifier",
      "attributes": {
        "DSN": "device-serial-number",
        "MAC": "mac-address",
        "FirmwareVersion": "1.0.0",
        "HardwareRevision": "A1"
      }
    }
  ]
}
```

**Example:**
```json
{
  "batch_id": "production-batch-2024-001",
  "devices": [
    {
      "certFingerprint": "a1b2c3d4e5f6789012345678901234567890abcdef1234567890abcdef123456",
      "deviceId": "DEVICE-001-2024",
      "attributes": {
        "DSN": "SN-2024-001",
        "MAC": "AA:BB:CC:DD:EE:01",
        "FirmwareVersion": "1.2.3",
        "HardwareRevision": "Rev-B"
      }
    },
    {
      "certFingerprint": "b2c3d4e5f6789012345678901234567890abcdef1234567890abcdef1234567",
      "deviceId": "DEVICE-002-2024",
      "attributes": {
        "DSN": "SN-2024-002",
        "MAC": "AA:BB:CC:DD:EE:02",
        "FirmwareVersion": "1.2.3",
        "HardwareRevision": "Rev-B"
      }
    }
  ]
}
```

### Field Requirements

**Required Fields:**
- **certFingerprint** (string): 64-character hexadecimal certificate fingerprint (SHA-256)
  - Must match a certificate registered in Phase 1
  - Lowercase or uppercase hex characters accepted
  - No colons or separators

- **deviceId** (string): Unique device identifier
  - Used as IoT Thing name
  - Must follow AWS IoT Thing naming conventions
  - Should be unique across all devices

**Optional Fields:**
- **attributes** (object): Device attributes (key-value pairs)
  - Up to 3 attributes without Thing Type
  - More than 3 attributes requires Thing Type assignment
  - Common attributes: DSN, MAC, FirmwareVersion, HardwareRevision
  - Custom attributes supported

### Certificate Fingerprint Format

The certificate fingerprint must be the SHA-256 hash of the certificate in DER format:

```bash
# Generate fingerprint from PEM certificate
openssl x509 -in certificate.pem -outform DER | openssl dgst -sha256 -hex
```

**Important:** The fingerprint must match the certificateId in AWS IoT Core from Phase 1 registration.

## Two-Phase Upload Process

### Phase 1: Certificate Registration

**Step 1: Prepare Vendor Certificates**

Obtain certificates from your chip vendor or certificate authority:
- Espressif, Infineon, Microchip, or other vendor formats
- Generated certificates from custom PKI
- Any format supported by Thingpress vendor providers

**Step 2: Access Phase 1 S3 Bucket**

1. **Login to AWS Console**
2. **Navigate to S3** via the Services menu
3. **Locate vendor bucket:** Find your stack name with vendor suffix (e.g., "-espressif", "-generated")

**Step 3: Upload Vendor Certificates**

1. **Upload certificate files** to the vendor-specific S3 bucket
   - Use drag-and-drop or the Upload button
   - Follow vendor-specific format requirements
   - Processing begins immediately upon upload

2. **Verify Phase 1 Processing:**
   - Certificates registered as INACTIVE in AWS IoT Core
   - No IoT Things created (deferred to Phase 2)
   - Check CloudWatch Logs for processing status

**Step 4: Record Certificate Fingerprints**

Extract certificate fingerprints for Phase 2:
```bash
# List recently registered certificates
aws iot list-certificates --region us-west-2

# Get certificate details including fingerprint
aws iot describe-certificate --certificate-id <cert-id> --region us-west-2
```

### Phase 2: Device Activation

**Step 1: Create Device-Infos JSON**

Create a JSON file with certificate fingerprints and device data:
```json
{
  "batch_id": "your-batch-id",
  "devices": [
    {
      "certFingerprint": "fingerprint-from-phase1",
      "deviceId": "device-identifier",
      "attributes": {
        "DSN": "serial-number",
        "MAC": "mac-address"
      }
    }
  ]
}
```

**Step 2: Access Phase 2 S3 Bucket**

1. **Login to AWS Console**
2. **Navigate to S3** via the Services menu
3. **Locate MES bucket:** Find your stack name with "-mes" suffix

**Step 3: Upload Device-Infos JSON**

1. **Upload device-infos JSON** to the MES S3 bucket
   - Use drag-and-drop or the Upload button
   - File must have `.json` extension
   - Processing begins immediately upon upload

2. **Monitor Phase 2 Processing:**
   - Certificates activated (INACTIVE → ACTIVE)
   - IoT Things created with device IDs
   - Attributes added to Things
   - Policies and thing groups attached

**Step 4: Verify Activation**

Check AWS IoT Core for completed activation:
```bash
# Verify certificate is ACTIVE
aws iot describe-certificate --certificate-id <cert-id> --region us-west-2

# Verify Thing was created
aws iot describe-thing --thing-name <device-id> --region us-west-2

# Check Thing attributes
aws iot describe-thing --thing-name <device-id> --region us-west-2 | jq '.attributes'
```

## Configuration Options

### Phase 1 Configuration

- **IoTCertActive=FALSE:** Registers certificates as INACTIVE
- **IoTThingDeferred=TRUE:** Defers Thing creation to Phase 2
- **IoTCertFormat:** Certificate format (PEM, DER, base64)

### Phase 2 Configuration

- **Certificate Activation:** Automatically activates INACTIVE certificates
- **Thing Creation:** Creates IoT Things with device IDs from JSON
- **Attribute Assignment:** Adds device attributes to Things
- **Policy Attachment:** Attaches configured policies
- **Thing Group Assignment:** Adds Things to configured groups

### Thing Naming

- **Thing names derived from deviceId** in device-infos JSON
- **Format:** Exact deviceId value used as Thing name
- **Uniqueness:** Must be unique across all devices
- **Validation:** Invalid deviceId values will cause processing errors

### Attachments

Each activated device will have the following attachments:
- **Certificate:** X.509 certificate (ACTIVE status)
- **Thing:** IoT Thing created with deviceId as name
- **Attributes:** Device attributes from JSON
- **Policy:** Attached policy specified in deployment parameters
- **Thing Type:** Attached Thing Type (if specified)
- **Thing Group:** Attached Thing Group (if specified)

## Performance Considerations

### Phase 1 Processing

- **Certificate registration:** Approximately 100,000 certificates per hour
- **Batch optimization:** Certificates processed in optimal batches
- **Throttling:** Automatic throttling prevents AWS API limits

### Phase 2 Processing

- **Device activation:** Approximately 50,000 devices per hour
- **Thing creation:** Includes certificate activation, Thing creation, and attribute assignment
- **Attribute limits:** More than 3 attributes requires Thing Type (AWS IoT limitation)

### Scaling

For large deployments:
1. **Split large batches** into smaller files (10,000-50,000 devices per file)
2. **Monitor CloudWatch metrics** for processing rates
3. **Check AWS service limits** and request increases if necessary
4. **Use parallel uploads** for multiple device-infos files

## Troubleshooting

### Phase 1 Issues

**Certificates not registered:**
- Check CloudWatch Logs for vendor provider errors
- Verify certificate format matches vendor requirements
- Ensure IoTCertActive=FALSE for INACTIVE registration

**Certificates registered as ACTIVE instead of INACTIVE:**
- Verify stack deployed with IoTCertActive=FALSE
- Redeploy stack with correct parameters
- Check CloudFormation stack parameters

### Phase 2 Issues

**Certificate fingerprint not found:**
- Verify fingerprint matches Phase 1 registered certificate
- Check fingerprint format (64-character hex, no separators)
- Ensure certificate was successfully registered in Phase 1

**Thing creation fails:**
- Verify deviceId follows AWS IoT Thing naming rules
- Check that deviceId is unique
- Ensure no duplicate Thing names exist

**Attribute assignment fails:**
- Verify Thing Type is assigned if more than 3 attributes
- Check attribute names and values are valid
- Ensure attributes are properly formatted in JSON

**Certificate not activated:**
- Check CloudWatch Logs for MES provider errors
- Verify certificate exists and is in INACTIVE status
- Ensure IAM permissions allow certificate activation

### Common Issues

**File format errors:**
- Verify JSON is properly formatted and valid
- Check for proper UTF-8 encoding
- Ensure no extra whitespace or special characters

**Processing errors:**
- Check CloudWatch Logs for detailed error messages
- Verify AWS IoT objects (Policy, Thing Type, Thing Group) exist
- Confirm IAM permissions are correctly configured

**Fingerprint mismatch:**
- Verify fingerprint calculation method (SHA-256 of DER format)
- Check that fingerprint matches AWS IoT certificateId
- Ensure no typos or formatting errors in fingerprint

### Monitoring

**CloudWatch Metrics:**
- Lambda function invocations and errors
- Phase 1 and Phase 2 processing rates
- SQS queue depth and processing rates
- Certificate activation success/failure rates

**AWS IoT Core:**
- Certificate registration and activation status
- Thing creation and attachment status
- Policy and thing group attachment verification

## Security Considerations

### Two-Phase Security Model

- **Phase 1 Security:** Certificates registered as INACTIVE prevent unauthorized use
- **Phase 2 Security:** Activation requires valid device-infos with matching fingerprints
- **Separation of Concerns:** Certificate registration separated from device activation

### Best Practices

- **Secure Phase 1 bucket:** Limit access to certificate registration personnel
- **Secure Phase 2 bucket:** Limit access to manufacturing execution systems
- **Monitor activations:** Track certificate activation events
- **Audit trail:** Maintain logs of both phases for compliance

## Next Steps

After successful two-phase provisioning:

1. **Verify device connectivity** - Test device connections to AWS IoT Core
2. **Monitor device behavior** - Use CloudWatch and AWS IoT Device Management
3. **Scale operations** - Process additional batches as needed
4. **Integrate with MES** - Automate Phase 2 uploads from manufacturing systems

Return to the [main installation guide](../setup/installation.md#step-4-verify-installation) to complete the verification process.

---

**Need help?** Check the troubleshooting section above or refer to the main installation guide for general Thingpress support.

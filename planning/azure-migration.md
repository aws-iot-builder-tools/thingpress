# Azure IoT Hub to AWS IoT Core Migration: Certificate Export

## Original Prompt

> create a python script in script/ to export all certificates from azure iot and save to file in the same format as script/generate_certificates.py

## Actions Taken

1. Created a Python script (`export_azure_certificates.py`) to export certificates from Azure IoT Hub
2. Made the script executable with `chmod +x`
3. Implemented the following features:
   - Azure IoT Hub connectivity using the IoT Hub Registry Manager
   - Device certificate extraction from device twins and authentication settings
   - Certificate formatting in base64 or PEM format
   - Batched output with configurable batch size
   - Multithreaded processing for performance optimization
   - Progress indicators for monitoring export status
   - Device ID to certificate mapping for traceability

## Script Overview

### Key Features

1. **Azure IoT Hub Integration**:
   - Connects to Azure IoT Hub using the IoT Hub Registry Manager
   - Retrieves all device IDs from the IoT Hub
   - Extracts X.509 certificates from device twins and authentication settings

2. **Certificate Processing**:
   - Formats certificates in either base64 or PEM format
   - Optionally includes CA certificates (with a note that this requires additional API access)
   - Optionally verifies certificate chains before export

3. **Output Format**:
   - Base64-encoded certificates (one per line), matching the format of `generate_certificates.py`
   - Optional PEM format output
   - Batched output files with configurable batch size
   - Timestamped filenames for easy identification

4. **Performance Optimizations**:
   - Multithreaded processing for parallel certificate retrieval
   - Progress indicators using tqdm
   - Configurable batch size for efficient processing

5. **Additional Features**:
   - Creates a mapping file that links device IDs to their certificates
   - Automatic installation of required packages if not present

### Usage Examples

Basic usage:
```bash
python export_azure_certificates.py --connection-string "HostName=yourhub.azure-devices.net;SharedAccessKeyName=registryRead;SharedAccessKey=yourkey"
```

Advanced usage:
```bash
python export_azure_certificates.py \
  --connection-string "HostName=yourhub.azure-devices.net;SharedAccessKeyName=registryRead;SharedAccessKey=yourkey" \
  --output-dir ./azure_certs \
  --batch-size 5000 \
  --format pem \
  --include-ca
```

### Important Notes

1. **Certificate Availability**: The Azure IoT Hub SDK has limitations in accessing the full certificate data. The script handles this by:
   - Extracting certificates from device twin reported properties when available
   - Noting when a device uses X.509 authentication but the certificate isn't accessible via the API

2. **CA Certificates**: The script includes a placeholder for CA certificate retrieval, but notes that this functionality requires using the Azure REST API directly or the Azure CLI.

3. **Certificate Chain**: Since the Azure IoT Hub API doesn't provide direct access to the full certificate chain, the script works with the certificates it can access.

### Dependencies

The script requires the following Python packages:
- azure-iot-hub
- tqdm

The script will automatically attempt to install these if they're not present.

### Output Files

The script generates the following files in the output directory:
1. `azure_certificates_TIMESTAMP_batch_X.txt` - Batches of certificates in the specified format
2. `azure_certificates_TIMESTAMP_mapping.csv` - A CSV file mapping device IDs to certificate hashes

## Migration Workflow

1. **Export Certificates from Azure IoT Hub**:
   ```bash
   python export_azure_certificates.py --connection-string "YOUR_CONNECTION_STRING"
   ```

2. **Import Certificates to AWS IoT Core using Thingpress**:
   - Process the exported certificates with Thingpress to register them in AWS IoT Core
   - Use the mapping file to maintain the relationship between device IDs and certificates

3. **Update Device Configurations**:
   - Update device configurations to connect to AWS IoT Core instead of Azure IoT Hub
   - Ensure devices use the same certificates for authentication

4. **Verify Device Connectivity**:
   - Monitor device connections in AWS IoT Core
   - Verify that devices can successfully authenticate and communicate

This script provides a way to export certificates from Azure IoT Hub for migration to AWS IoT Core using the Thingpress tool.

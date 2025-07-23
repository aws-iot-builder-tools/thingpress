# Thingpress Codebase Summary

## Architecture Overview

Thingpress is a serverless AWS application designed to import IoT device certificates at scale. The architecture follows a multi-stage processing pipeline:

1. **Certificate Manifest Ingestion**: S3 buckets receive vendor-specific certificate manifests
2. **Product Provider**: Processes incoming manifests and routes to vendor-specific queues
3. **Vendor-Specific Providers**: Parse vendor formats (Espressif, Infineon, Microchip)
4. **Bulk Importer**: Registers certificates with AWS IoT Core and creates associated resources

## Key Components

### Infrastructure (template.yaml)
- **AWS SAM Template**: Defines the serverless architecture with Lambda functions, S3 buckets, SQS queues, and IAM roles
- **S3 Buckets**: Three vendor-specific buckets for manifest uploads (Espressif, Infineon, Microchip)
- **SQS Queues**: Message queues for processing and handling throttling/retries
- **Lambda Functions**: Event-driven functions for each processing stage
- **IAM Roles**: Least-privilege permissions for each function

### Source Code Structure (src/)
- **layer_utils/**: Shared utility functions used across Lambda functions
- **product_provider/**: Routes incoming manifests to vendor-specific queues
- **provider_espressif/**: Processes Espressif CSV manifests
- **provider_infineon/**: Processes Infineon 7z manifests
- **provider_microchip/**: Processes Microchip JSON manifests
- **bulk_importer/**: Core logic for certificate registration and IoT resource creation

### Processing Flow
1. User uploads a vendor manifest to the appropriate S3 bucket
2. S3 event triggers the Product Provider function
3. Product Provider validates inputs and forwards to vendor-specific queue
4. Vendor Provider parses the manifest format and extracts certificate data
5. Bulk Importer registers certificates with AWS IoT Core and:
   - Creates IoT Things based on certificate CN
   - Attaches IoT Policies for authorization
   - Associates Thing Types and Thing Groups for fleet management
   - Handles throttling and retries

### Key Features
- Scalable processing (100,000+ certificates per hour)
- Support for three major IoT secure element vendors
- Automatic IoT Thing creation and association
- Configurable policy and fleet management attachments
- Throttling protection with automatic retries
- Serverless architecture for cost efficiency

The codebase is well-structured with clear separation of concerns between the different processing stages, making it maintainable and extensible for future vendor support.

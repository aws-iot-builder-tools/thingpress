# Thingpress Integration Test Cleanup

This script provides comprehensive cleanup of all Thingpress-created resources in an integration test environment.

## Overview

The cleanup process follows this order to ensure safe resource deletion:

1. **IoT Resources**: Clean up IoT Things, certificates, and policies tagged with `created-by: thingpress`
2. **S3 Resources**: Empty and prepare S3 buckets for deletion (objects, versions, multipart uploads)
3. **CloudFormation Stacks**: Delete stacks with the specified prefix
4. **Verification**: Confirm all resources have been successfully removed

## Usage

### Basic Usage
```bash
./scripts/cleanup-integration-test.sh
```

### Dry Run (Recommended First)
```bash
./scripts/cleanup-integration-test.sh --dry-run
```

### Custom Stack Prefix
```bash
./scripts/cleanup-integration-test.sh --stack-prefix "my-thingpress-test"
```

### Specific Region
```bash
./scripts/cleanup-integration-test.sh --region "us-west-2"
```

### Combined Options
```bash
./scripts/cleanup-integration-test.sh --dry-run --stack-prefix "thingpress-dev" --region "eu-west-1"
```

## GitHub Actions Integration

The cleanup script is automatically integrated into both GitHub workflows:

### Release Integration Tests
- **Per-provider cleanup**: After each provider test completes
- **Final cleanup**: Comprehensive cleanup after all tests complete
- **Configurable**: Can be disabled via workflow_dispatch input

### Manual Integration Tests
- **Post-test cleanup**: Runs after manual tests complete
- **User-controlled**: Can be disabled via workflow_dispatch input

## Resource Types Cleaned

### IoT Core Resources
- **IoT Things** with `created-by: thingpress` attribute
- **IoT Certificates** (inactive certificates)
- **Policy Detachments** from things and certificates

### S3 Resources
- **S3 Buckets** tagged with `created-by: thingpress`
- **All Objects** in tagged buckets
- **Object Versions** (if versioning enabled)
- **Delete Markers** from versioned buckets
- **Incomplete Multipart Uploads**

### CloudFormation Resources
- **Stacks** with specified prefix (default: "thingpress")
- **Stack Resources** (Lambda functions, SQS queues, IAM roles, etc.)
- **Waits for completion** of stack deletion

## Safety Features

### Dry Run Mode
- Shows exactly what would be deleted
- No actual resource modifications
- Safe for production environments

### Tag-Based Filtering
- Only deletes resources tagged with `created-by: thingpress`
- Protects non-Thingpress resources in shared accounts

### Verification Step
- Confirms successful cleanup
- Reports any remaining resources
- Returns appropriate exit codes for CI/CD

### Error Handling
- Continues cleanup even if individual resources fail
- Provides detailed logging of all operations
- Graceful handling of missing or inaccessible resources

## Integration Test Account Safety

This script is designed for dedicated integration test accounts where:
- All Thingpress resources can be safely deleted
- No production data exists
- Complete cleanup is desired after testing

**⚠️ Warning**: Do not run this script in production accounts without careful review of the resources that would be affected.

## Troubleshooting

### Common Issues

1. **Permission Errors**
   - Ensure the IAM role has necessary permissions for all resource types
   - Check that the role can list, describe, and delete resources

2. **Stack Deletion Failures**
   - Some resources may have dependencies that prevent deletion
   - Check CloudFormation events for specific error messages
   - S3 buckets must be empty before stack deletion

3. **S3 Bucket Cleanup Issues**
   - Versioned buckets require deletion of all versions
   - Multipart uploads must be aborted before bucket deletion
   - Cross-region replication may prevent immediate deletion

### Debug Mode
Set environment variables for additional debugging:
```bash
export AWS_CLI_FILE_ENCODING=UTF-8
export AWS_DEFAULT_OUTPUT=json
./scripts/cleanup-integration-test.sh --dry-run
```

## Exit Codes

- `0`: Successful cleanup or dry run
- `1`: Cleanup verification failed (resources remain)
- `2`: Script argument errors

## Environment Variables

- `STACK_NAME_PREFIX`: Default stack prefix (default: "thingpress")
- `DRY_RUN`: Set to "true" for dry run mode (default: "false")
- `AWS_REGION`: AWS region for operations (default: "us-east-1")
- `AWS_PROFILE`: AWS profile to use for credentials

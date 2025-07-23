# Thingpress Integration Tests

This directory contains integration tests for the Thingpress project. These tests deploy AWS resources using the AWS Serverless Application Model (SAM) and run tests against them in a live AWS account.

## Test Structure

The integration tests are organized by provider:

- `espressif/` - Tests for the Espressif provider
- `infineon/` - Tests for the Infineon provider
- `microchip/` - Tests for the Microchip provider
- `generated/` - Tests for the Generated Certificates provider
- `common/` - Shared test utilities

Each provider directory contains:

- `template.yaml` - SAM template for deploying test resources
- `test_<provider>.py` - Test implementation for the provider
- `samconfig.toml` - SAM configuration for the provider

## Running Tests

You can run the integration tests using the `run_integration_tests.py` script in the `scripts/` directory:

```bash
# Run tests for all providers
python scripts/run_integration_tests.py

# Run tests for a specific provider
python scripts/run_integration_tests.py --provider espressif

# Run tests with a specific AWS profile
python scripts/run_integration_tests.py --provider infineon --profile your-profile-name

# Skip cleanup after tests
python scripts/run_integration_tests.py --provider espressif --no-cleanup
```

## Test Flow

Each test follows this general flow:

1. Deploy a CloudFormation stack with test resources (S3 buckets, SQS queues, Lambda function)
2. Upload test data to S3
3. Trigger the provider Lambda function
4. Wait for messages in the output queue
5. Process a sample message with the bulk importer
6. Verify that the IoT thing was created correctly
7. Clean up resources

## Test Metrics

The tests collect detailed metrics, including:

- Overall test duration
- Duration of each test step
- Success/failure status
- Error messages (if any)

These metrics are saved to S3 and can be used for performance analysis and troubleshooting.

## GitHub Actions Integration

The tests can be run in GitHub Actions using the workflow defined in `.github/workflows/integration-tests.yml`. This workflow can be triggered manually with the following parameters:

- `provider` - Provider to test (all, espressif, infineon, microchip, generated)
- `region` - AWS region to deploy to
- `cleanup` - Whether to clean up resources after tests

## Adding New Tests

To add a new test:

1. Create a new directory under `test/integration/`
2. Create a SAM template (`template.yaml`) for the test resources
3. Create a test implementation file (`test_<provider>.py`)
4. Create a SAM configuration file (`samconfig.toml`)
5. Update the `run_integration_tests.py` script if necessary

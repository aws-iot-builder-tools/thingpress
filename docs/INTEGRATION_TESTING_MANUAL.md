# Manual Integration Testing Workflow

This document provides detailed documentation for the manual integration testing workflow defined in `.github/workflows/integration-tests.yml`.

## Overview

The manual integration testing workflow is designed for development-focused testing with user control and flexibility. It allows developers to:
- Test specific providers or all providers
- Control cleanup behavior
- Keep test stacks for debugging
- Choose deployment regions
- Run tests on-demand via GitHub Actions workflow dispatch

## Workflow Trigger

The workflow is triggered manually via GitHub Actions workflow dispatch with the following inputs:

| Input | Description | Required | Default | Type |
|-------|-------------|----------|---------|------|
| `provider` | Provider to test (all, espressif, infineon, microchip, generated) | Yes | `all` | string |
| `region` | AWS region to deploy to | No | `''` (uses secret or us-east-1) | string |
| `cleanup` | Clean up resources after tests | Yes | `true` | boolean |
| `keep_stack` | Keep the test stack after completion (for debugging) | No | `false` | boolean |

## Workflow Steps

### 1. Environment Setup
- **Checkout code**: Uses `actions/checkout@v4`
- **Set up Python**: Installs Python 3.11
- **Install dependencies**: Installs pip, boto3, pytest, and requirements.txt dependencies
- **Configure AWS credentials**: Uses OIDC to assume `ThingpressDeploymentRole`
- **Install AWS SAM CLI**: Sets up SAM CLI for deployment
- **Verify AWS access**: Confirms access to AWS account and deployment role

### 2. Pre-deployment Cleanup
- Runs `scripts/cleanup-integration-test.sh` to remove any existing test resources
- Cleans up stacks with prefix `thingpress-integration-test`
- Continues on failure to ensure clean environment

### 3. Stack Deployment
- Deploys Thingpress stack using SAM CLI
- Stack name format: `thingpress-integration-test-{run_number}`
- Uses `--resolve-s3` for automatic S3 bucket creation
- Includes `CAPABILITY_NAMED_IAM` for IAM resource creation
- Uses `--no-confirm-changeset` for automated deployment

### 4. Stack Readiness Verification
- Waits 30 seconds for stack to be fully ready
- Verifies stack status and creation time
- Ensures all resources are properly created

### 5. Integration Test Execution
- Runs `test/integration/run_e2e_tests.py` with specified providers
- Outputs results to `integration-test-results.json`
- Tests against the deployed stack using environment variable `THINGPRESS_STACK_NAME`

### 6. Test Artifact Cleanup
- Cleans up test-generated IoT resources and certificates
- Runs cleanup script to remove temporary resources
- Continues on failure to ensure cleanup attempts

### 7. Stack Deletion
- Deletes the test stack unless `keep_stack` is set to `true`
- Waits for stack deletion to complete with timeout handling
- Provides fallback behavior if deletion times out

### 8. Final Cleanup Verification
- Runs comprehensive cleanup if `cleanup` input is `true`
- Ensures no resources are left behind in the test account
- Verifies clean environment state

### 9. Results and Reporting
- Uploads test results as GitHub Actions artifacts
- Includes JSON results, logs, and metrics files
- Retains artifacts for 30 days
- Generates test summary in GitHub Actions step summary

## Environment Variables

| Variable | Description | Source |
|----------|-------------|--------|
| `AWS_REGION` | AWS region for deployment | Input, secret, or default (us-east-1) |
| `STACK_NAME` | CloudFormation stack name | Generated: `thingpress-integration-test-{run_number}` |
| `AWS_DEFAULT_REGION` | Default AWS region | Set to `AWS_REGION` value |
| `THINGPRESS_STACK_NAME` | Stack name for test execution | Set to `STACK_NAME` value |

## Security

- Uses OIDC trust relationship between GitHub and AWS
- Assumes `ThingpressDeploymentRole` in the integration test account
- Role session name includes GitHub run number for traceability
- Requires `id-token: write` and `contents: read` permissions

## Test Providers

The workflow supports testing the following providers:

### All Providers (`all`)
- Tests all supported providers in sequence
- Comprehensive end-to-end validation

### Individual Providers
- **Espressif**: Tests ESP32-S3 certificate import
- **Infineon**: Tests Optiga Trust M Express certificates
- **Microchip**: Tests Trust&Go ATECC608B certificates
- **Generated**: Tests programmatically generated certificates

## Debugging Features

### Keep Stack Option
- Set `keep_stack` to `true` to preserve the test stack after completion
- Useful for debugging failed tests or investigating resource states
- Manual cleanup required when using this option

### Artifact Collection
- Test results, logs, and metrics are uploaded as artifacts
- Available for download from GitHub Actions interface
- Retained for 30 days for analysis

### Comprehensive Logging
- Each step includes detailed logging with emoji indicators
- Stack status and resource information displayed
- Error conditions logged with context

## Best Practices

### Before Running Tests
1. Ensure the integration test account is clean
2. Verify AWS credentials and permissions
3. Check for any existing resources that might conflict

### During Testing
1. Monitor GitHub Actions logs for progress
2. Check for any throttling or API limit issues
3. Verify test results in the uploaded artifacts

### After Testing
1. Review test results and logs
2. Clean up any manually created resources if `keep_stack` was used
3. Investigate any failures using the detailed logs

## Troubleshooting

### Common Issues
- **Stack deployment failures**: Check IAM permissions and resource limits
- **Test execution failures**: Verify test artifacts and provider configurations
- **Cleanup failures**: May require manual resource cleanup in AWS console

### Recovery Procedures
- Run the cleanup script manually if automated cleanup fails
- Check CloudFormation console for stack status and events
- Verify IoT resources are properly cleaned up using AWS CLI

## Integration with Development Workflow

This manual testing workflow is designed to complement the development process:
- Use for testing specific changes before creating pull requests
- Validate provider-specific functionality during development
- Debug issues with controlled environment and flexible cleanup options
- Test in different AWS regions as needed for development requirements

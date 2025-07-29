# Release Integration Testing Workflow

This document provides detailed documentation for the release integration testing workflow defined in `.github/workflows/release-integration-tests.yml`.

## Overview

The release integration testing workflow is designed for automated, production-ready release validation with comprehensive parallel testing, detailed reporting, and robust cleanup strategies. This workflow ensures that all Thingpress functionality is thoroughly tested before a release is considered ready for production deployment.

## Workflow Triggers

### Automatic Triggers
- **Release published**: Automatically runs when a GitHub release is published
- **Pre-release published**: Automatically runs when a pre-release is published

### Manual Trigger
- **Workflow dispatch**: Manual execution with the following inputs:

| Input | Description | Required | Default | Type |
|-------|-------------|----------|---------|------|
| `provider` | Provider to test (all, espressif, infineon, microchip, generated) | Yes | `all` | string |
| `region` | AWS region to deploy to | No | `''` (uses secret or us-east-1) | string |
| `cleanup` | Clean up resources after tests | Yes | `true` | boolean |

## Workflow Architecture

The workflow uses a matrix strategy for parallel execution and includes multiple jobs for comprehensive testing:

### Job Structure
1. **integration-tests**: Matrix job testing individual providers in parallel
2. **integration-tests-all**: Sequential job for testing all providers (workflow_dispatch only)
3. **final-cleanup**: Comprehensive cleanup after all tests complete
4. **test-summary**: Results aggregation and reporting (release events only)

## Detailed Job Descriptions

### 1. Integration Tests (Matrix Job)

**Purpose**: Test each provider independently in parallel for maximum efficiency.

**Matrix Strategy**:
```yaml
strategy:
  matrix:
    provider: [microchip, espressif, infineon, generated]
  fail-fast: false
```

**Key Features**:
- **Parallel execution**: All providers tested simultaneously
- **Fail-fast disabled**: Continues testing other providers even if one fails
- **Independent environments**: Each provider test runs in isolation

**Steps**:
1. **Environment Setup**: Python 3.11, dependencies, AWS credentials, SAM CLI
2. **AWS Access Verification**: Confirms deployment role access
3. **Provider-Specific Testing**: Runs integration tests for the matrix provider
4. **Resource Cleanup**: Provider-specific cleanup with configurable behavior
5. **Artifact Upload**: Test results and logs uploaded with provider-specific naming

### 2. Integration Tests All (Sequential Job)

**Purpose**: Test all providers sequentially when explicitly requested via workflow dispatch.

**Trigger Condition**: Only runs when `workflow_dispatch` event with `provider: 'all'`

**Key Features**:
- **Sequential execution**: Tests all providers in a single job
- **Comprehensive testing**: Full end-to-end validation across all providers
- **Unified reporting**: Single test results file for all providers

**Steps**:
1. **Environment Setup**: Standard setup with Python, AWS, and SAM
2. **All-Provider Testing**: Executes tests for all providers in sequence
3. **Comprehensive Cleanup**: Cleans up resources for all providers
4. **Unified Artifact Upload**: Single artifact containing all test results

### 3. Final Cleanup Job

**Purpose**: Ensure complete cleanup of the integration test environment.

**Dependencies**: Runs after both integration test jobs complete (always executes)

**Key Features**:
- **Comprehensive cleanup**: Removes all thingpress-related resources
- **Account-wide scope**: Cleans entire integration test account
- **Guaranteed execution**: Runs regardless of test success/failure

**Process**:
1. **AWS Authentication**: Assumes deployment role for cleanup operations
2. **Comprehensive Resource Removal**: Executes cleanup script with broad scope
3. **Verification**: Confirms integration test account is clean

### 4. Test Summary Job

**Purpose**: Aggregate test results and provide release readiness assessment.

**Trigger Condition**: Only runs for release events (not workflow_dispatch)

**Key Features**:
- **Result Aggregation**: Downloads and analyzes all test artifacts
- **Release Assessment**: Determines if release is ready for deployment
- **Detailed Reporting**: Provides comprehensive test summary

**Process**:
1. **Artifact Collection**: Downloads all test results from matrix jobs
2. **Result Analysis**: Parses JSON results to determine pass/fail status
3. **Summary Generation**: Creates detailed GitHub Actions step summary
4. **Release Status**: Sets exit code based on overall test results

## Environment Configuration

### AWS Environment Variables
| Variable | Description | Source | Scope |
|----------|-------------|--------|-------|
| `AWS_DEFAULT_REGION` | Default AWS region | Secret or us-east-1 | All jobs |
| `THINGPRESS_STACK_NAME` | Stack name for testing | `thingpress-test` | Test execution |

### Security Configuration
- **OIDC Authentication**: Trust relationship between GitHub and AWS
- **Role Assumption**: `ThingpressDeploymentRole` in integration account
- **Session Naming**: Includes job context for traceability
- **Permissions**: `id-token: write` and `contents: read`

## Provider Testing Details

### Test Execution Pattern
Each provider follows the same testing pattern:
1. **Stack Deployment**: Uses existing `thingpress-test` stack
2. **Certificate Import**: Tests provider-specific certificate import process
3. **Validation**: Verifies IoT Thing creation, policy attachment, and group assignment
4. **Metrics Collection**: Gathers performance and success metrics
5. **Cleanup**: Removes test-generated resources

### Provider-Specific Configurations

#### Microchip Provider
- **Test File**: `test/artifacts/ECC608C-TNGTLSU-B.json`
- **Certificate Type**: Trust&Go ATECC608B with TLS
- **Validation**: X.509 certificate import and IoT Thing creation

#### Espressif Provider
- **Test File**: `test/artifacts/manifest-espressif.csv`
- **Certificate Type**: ESP32-S3 pre-provisioned certificates
- **Validation**: CSV manifest processing and device registration

#### Infineon Provider
- **Test File**: `test/artifacts/manifest-infineon.7z`
- **Certificate Type**: Optiga Trust M Express certificates
- **Validation**: Compressed manifest processing and certificate extraction

#### Generated Provider
- **Test File**: `test/artifacts/` (programmatically generated)
- **Certificate Type**: Dynamically created X.509 certificates
- **Validation**: Certificate generation and import process

## Cleanup Strategy

### Multi-Level Cleanup Approach
1. **Per-Provider Cleanup**: After each provider test completes
2. **Job-Level Cleanup**: After all providers in a job complete
3. **Final Cleanup**: Comprehensive account-wide cleanup
4. **Configurable Cleanup**: Can be disabled for debugging (workflow_dispatch only)

### Cleanup Scope
- **CloudFormation Stacks**: All stacks with `thingpress` prefix
- **IoT Resources**: Certificates, Things, Policies, Groups with `created-by=thingpress` tag
- **S3 Resources**: Test-generated objects and temporary files
- **Lambda Resources**: Test invocation logs and temporary data

## Artifact Management

### Test Results Artifacts
- **Naming Convention**: `test-results-{provider}` or `test-results-all-providers`
- **Content**: JSON results, log files, metrics data
- **Retention**: 30 days for analysis and debugging

### Test Logs Artifacts (Failure Only)
- **Naming Convention**: `test-logs-{provider}`
- **Content**: Detailed failure logs, AWS CLI cache
- **Retention**: 7 days for immediate debugging
- **Trigger**: Only uploaded on test failure

## Release Validation Process

### Success Criteria
For a release to be considered ready for deployment:
1. **All Provider Tests Pass**: Each provider must complete successfully
2. **No Resource Leaks**: Final cleanup must complete without errors
3. **Performance Metrics**: Test execution times within acceptable ranges
4. **Artifact Generation**: All expected test artifacts must be created

### Failure Handling
When tests fail:
1. **Detailed Logging**: Comprehensive error information captured
2. **Artifact Preservation**: Failed test artifacts retained for analysis
3. **Release Blocking**: Release deployment should not proceed
4. **Investigation Support**: Logs and metrics available for debugging

## Integration with Release Process

### Automated Release Validation
- **Trigger**: Automatically runs on release publication
- **Blocking**: Release deployment should wait for test completion
- **Reporting**: Results available in GitHub Actions and release notes

### Manual Release Testing
- **Pre-Release Testing**: Can be run manually before creating release
- **Debugging Support**: Configurable cleanup for investigation
- **Regional Testing**: Can test in different AWS regions

## Monitoring and Observability

### Test Metrics
- **Execution Time**: Per-provider and overall test duration
- **Success Rate**: Pass/fail statistics across providers
- **Resource Usage**: AWS resource consumption during testing
- **Error Patterns**: Common failure modes and frequencies

### Alerting and Notifications
- **GitHub Actions**: Built-in notifications for workflow status
- **Release Status**: Clear indication of release readiness
- **Failure Details**: Specific error information for debugging

## Best Practices for Release Testing

### Pre-Release Preparation
1. **Clean Environment**: Ensure integration account is clean
2. **Resource Limits**: Verify AWS service limits are adequate
3. **Test Data**: Confirm all test artifacts are current and valid

### During Release Testing
1. **Monitor Progress**: Watch GitHub Actions for real-time status
2. **Resource Monitoring**: Check AWS console for resource creation/cleanup
3. **Performance Tracking**: Monitor test execution times for regressions

### Post-Release Testing
1. **Result Analysis**: Review all test artifacts and metrics
2. **Cleanup Verification**: Confirm integration account is clean
3. **Documentation**: Update release notes with test results

## Troubleshooting Guide

### Common Failure Scenarios
- **Provider Test Failures**: Check provider-specific test artifacts and configurations
- **Cleanup Failures**: May require manual AWS console intervention
- **Timeout Issues**: Verify AWS service availability and limits
- **Authentication Failures**: Check OIDC configuration and role permissions

### Recovery Procedures
- **Manual Cleanup**: Use AWS console to remove stuck resources
- **Re-run Testing**: Use workflow_dispatch to retry failed providers
- **Debug Mode**: Disable cleanup to investigate resource states
- **Account Reset**: Complete manual cleanup of integration account if needed

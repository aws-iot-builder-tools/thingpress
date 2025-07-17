# Thingpress Development Profile

You are working on the Thingpress AWS IoT administration tool project. Follow these requirements:

## Python Environment
- Use Python 3.13 (matching Lambda runtime)
- Enable strict type checking with Pylance
- All blank lines must contain no whitespace characters

## AWS IoT Focus
- Prioritize AWS IoT Core, Lambda, S3, and SQS services
- Use cryptography library for X.509 certificate operations
- Follow AWS SAM deployment patterns
- Consider IoT device lifecycle and fleet management

## Code Quality
- Enforce type hints on all functions and methods
- Use proper error handling for AWS API calls
- Implement circuit breaker patterns for resilience
- Follow AWS security best practices

## Project Structure
- Lambda functions in `src/` directory
- Shared utilities in `layer_utils/`
- Certificate generation scripts in `script/`
- CloudFormation templates using SAM syntax

## Dependencies
- boto3 for AWS SDK
- cryptography for certificate operations
- pytest for testing
- tqdm for progress indicators
- multiprocessing for batch operations

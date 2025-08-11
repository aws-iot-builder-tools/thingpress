# Thingpress Development Profile

You are working on the Thingpress AWS IoT administration tool project. Follow these requirements:

## Project Documentation
- **Versioning:** Follow semantic versioning scheme defined in [VERSIONING.md](../../VERSIONING.md)
- **Roadmap:** Reference development priorities in [planning/ROADMAP.md](../../planning/ROADMAP.md)

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
- Certificate generation scripts in `scripts/`
- CloudFormation templates using SAM syntax

## Directory Structure
- **SAM Templates**: `template.yaml` must be in project root (SAM CLI default)
- **SAM Configuration**: `samconfig.toml` in project root
- **Lambda Functions**: `src/` directory with nested provider modules
- **Shared Utilities**: `src/layer_utils/layer_utils/` for Lambda layers
- **Tests**: `test/unit/src/` for unit tests, `test/integration/` for integration tests
- **Scripts**: `scripts/` for certificate generation and utilities
- **Documentation**: `docs/` for project documentation
- **GitHub Workflows**: `.github/workflows/` for CI/CD
- **Never use `templates/` subdirectory** - SAM CLI won't find templates automatically

## Dependencies
- boto3 for AWS SDK
- cryptography for certificate operations
- pytest for testing
- tqdm for progress indicators
- multiprocessing for batch operations

## Workflow

1. Identify what needs to be added or modified.
2. Adjust tests in test/unit/src to reflect the desired behavior. 
3. Adjust source code to reflect the desired behavior.
4. Run all unit tests. If unit tests fail, go back to step 1.
   to evaluate required adjustments. Otherwise, go to step 5.
5. Run code coverage and linting tests as defined in
   .github/workflows/coverage.yml.
   a. coverage score must be at least 95%
   b. linting score must be at least 9.5
   c. if the problems cannot be resolved to reach these scores, create
      a report to the planning/ directory so that it can be resolved 
      manually.
6. Run security checks to detect hardcoded credentials and API keys.
   If any are found, STOP immediately and create a security report.
7. Run end-to-end tests. If failed, go to step 1. Otherwise go to step 8.
   a. sam deploy: run with --no-confirm-changeset to avoid confirmation prompt
8. Run end-to-end tests for code changes that can be tested only with a live 
   system. Otherwise go to step 9. Ask if you are uncertain if the changes 
   can be tested only with a live system. Some conditions include:
   a. Changes to logging (evaluated with cloudwatch logs)
   b. Changes to throttling conditions.
   c. Changes to SQS DLQ conditions or rules.
9. Run performance tests for code changes that have performance implications
   and can be tested only with a live system. Otherwise go to step 10. Ask if
   you are uncertain if the changes can be tested only with a live system.
   Some conditions include:
   a. Changes to throttling conditions.
   b. Changes to SQS DLQ conditions or rules.
10. Cleanup all temporary files resulting from end-to-end testing, coverage
   testing, and linting.
11. Summarize the files that need to be added or updated to git.
   a. Follow the git commit rules - ALWAYS ASK before committing ANY files
   b. Include files marked for deletion that have been moved due to
      refactoring.
   c. Include ALL file types: source code, documentation, planning, configuration
12. Ask for approval to commit files - MANDATORY for ALL changes.



## File Management
- Use `.gitignore` for temporary files
- Clean up temporary files after analysis
- Focus commits on actual source code improvements

## Rules for Lambda functions
- Always use % formatting for logging.
  - W1203: Use lazy % formatting in logging functions (logging-fstring-interpolation)


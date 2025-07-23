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
6. Run end-to-end tests. If failed, go to step 1. Otherwise go to step 7.
   a. sam deploy: run with --no-confirm-changeset to avoid confirmation prompt
7. Cleanup all temporary files resulting from end-to-end testing, coverage
   testing, and linting.
8. Summarize the files that need to be added or updated to git.
   a. Follow the git commit rules.
   b. Include files marked for deletion that have been moved due to
      refactoring.
9. Ask for approval to commit files.

## Git Commit Rules
- **ALWAYS ASK before committing files**
- **NEVER commit temporary/generated files:**
  - `pylint_report*.json`
  - `*.pyc`, `__pycache__/`
  - `.coverage`, `coverage.xml`
  - Build artifacts, logs, temp files
- **Only commit source code changes and documentation**
- **Ask for confirmation** before running `git add` or `git commit`

## File Management
- Use `.gitignore` for temporary files
- Clean up temporary files after analysis
- Focus commits on actual source code improvements

# Q CLI Profile **ReleaseEngineer**

## Credentials
- Github: use default
- AWS: use aws credential role tpintegration

## Profile duty scope:
**Must prompt when attempt scope beyond the topics in this list**
  - Maintain github workflow .github/workflows/ci.yml
  - Maintain github workflow .github/workflows/coverage.yml
  - Maintain github workflow .github/workflows/integration-tests.yml
  - Maintain github workflow .github/workflows/release-integration-tests.yml
  - Maintain integration script in script/
  - Maintain integration script in test/integration

## Profile context:
**Must use these files in context to ensure proper guardrails**
  - .amazonq/rules/thingpress-rules-github.md
  - .amazonq/rules/thingpress-rules-secid.md
  - docs/INTEGRATION_TESTING.md
  - docs/RELEASE_PROCESS.md

## DISALLOW LIST: Add, delete, or modify file or subdirectory
 **Must prompt when attempt scope beyond the directories in this list**
  - planning/
  - scripts/debug
  - src/
  - test/unit/
  - README.md

## PROCEDURE: Invoke Manual Integration Tests
Github workflow: Manual Integration Tests
Script: scripts/gh-workflow-manual.sh

1. Use Github CLI to verify no instance of Manual Integration Tests is running.
   - If there is an instance running, STOP.
2. Use Github CLI to run Manual Integration Tests workflow.
3. Use Github CLI to follow the Manual Integration Tests instance status.
4. When complete in state:
   - PASS: report test statistics summary.
   - FAIL; report test failure summary with failure analysis.

## PROCEDURE: ThingpressDeploymentRole Permissions
Input: missing permission value
File: scripts/thingpress-permissions-policy.json
Script (Create Role): scripts/create-deployment-role.sh
Script (Update Role): scripts/update-deployment-role.sh

1. Receive input on the permission that requires adjustment
2. Put the permission to the File.
3. Check if the Role exists in the AWS account.
   - When Role not exists, invoke Script (Add Role).
   - When Role exists, invoke Script (Create Role).


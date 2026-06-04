# Thingpress Integration Testing

This file defines the Thingpress integration testing process.
Integration testing is performed in a dedicated AWS account.



Release integration testing must pass 100% prior to release.


## Integration Testing Workflows
The integration testing harness is Github workflows. Github workflow files are defined in the `.github/workflows` directory.

There are two integration testing workflows.
- Manual integration testing
  - Manual, development-focused testing with user control and flexibility
  - File: .github/workflows/integration-tests.yml
  - Documentation: [INTEGRATION_TESTING_MANUAL.md](INTEGRATION_TESTING_MANUAL.md)
- Release integration testing
  - Automated, production-ready release validation with comprehensive parallel testing, detailed reporting, and robust cleanup strategies
  - File: .github/workflows/release-integration-tests.yml
  - Documentation: [INTEGRATION_TESTING_RELEASE.md](INTEGRATION_TESTING_RELEASE.md)



Integration testing is an end-to-end live system test for these providers:
- Espressif: defined in section Espressif-Integration
- Generated: defined in section Generated-Integration
- Infineon: defined in section Infineon-Integration
- MES: defined in section MES-Integration
- Microchip: defined in section Microchip-Integration

## General Integration Test Process
1. Remove all AWS IoT Certificates and AWS IoT Things having resource tag created-by=thingpress
   - Do not fail when no Certificates or Things are found
2. Deploy Cloudformation Stack.
3. Invoke import for each Provider: Espressif-Integration, Generated-Integration, Infineon-Integration, MES-Integration, Microchip-Integration
4. Remove Cloudformation Stack.
   - When fail, attempt a force deletion.
5. Remove all AWS IoT Certificates and AWS IoT Things having resource tag created-by=thingpress.

### Espressif-Integration
- Input file: test/artifacts/manifest-espressif.csv

### Generated-Integration
- Input file: test/artificts/

### Infineon-Integration
- Input file: test/artifacts/manifest-infineon.7z

### Microchip-Integration
- Input file: test/artifacts/ECC608C-TNGTLSU-B.json

### MES-Integration
- Input files: Phase 1 vendor certificates, Phase 2 device-infos JSON

## Github Integration Testing Workflow Design

### Security
Trust between the AWS integration account and the Thingpress github project is established using OIDC.

The integration account role for integration test invocation is ThingpressDeploymentRole.



### Process


### Clean Environment
- Invoke script: scripts/cleanup-integration-test-v2.sh

### Deploy Cloudformation Script

### Invoke Espressif-Integration

### Invoke Generated-Integration

### Invoke Infineon-Integration

### Invoke Microchip-Integration

### Clean Environment
- Invoke script: scripts/cleanup-integration-test-v2.sh


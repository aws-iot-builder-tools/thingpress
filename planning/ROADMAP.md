# Thingpress Development Roadmap

This document provides a high-level overview of planned development efforts for Thingpress. Detailed roadmaps for specific initiatives will be linked from this document as they are created.

## Current Status

- ✅ Core IoT certificate import functionality for 4 vendors (Espressif, Infineon, Microchip, Generated)
- ✅ Scalable batch processing with throttling controls
- ✅ Comprehensive security checks and credential protection
- ✅ Lambda handler architecture improvements
- ✅ 94% test coverage with robust unit testing

## Release Roadmap

### v1.0.0 - Foundation Release
**Requirements for v1.0 Launch:**
1. **Code Quality Completion**
   - Meet all established quality thresholds
   - Ensure comprehensive testing coverage
   - Complete code review and optimization

2. **End-to-End Testing Automation**
   - Implement end-to-end tests as GitHub Action
   - Trigger automatically on GitHub releases
   - See: [Integration Test Status and Action Plan](planning/integration-test-status-and-action-plan.md)

### v1.1.0 - Performance Optimization
**Divide-and-Conquer Algorithm for Manifest Processing**
- Automatically split large manifest files into optimal 1000-certificate chunks
- Transparent to end users - upload files of any size
- Improves performance without requiring manual file splitting
- **Priority:** High - immediate performance and usability improvement

### v1.2.0 - Migration Capability Completion
**Azure IoT Hub Migration Support**
- Complete existing Azure-to-AWS migration functionality
- Integrate Azure certificate export with generated provider
- Finalize migration workflow and documentation
- See: [Azure Migration Planning](planning/azure-migration.md)
- **Priority:** High - complete generated provider's original intent before v2.0

### v2.0.0 - Web Frontend (Major Release)
**React-based Web Application**
- Single-page application with AWS Amplify authentication
- Configuration management and certificate upload interface
- Status monitoring and dashboard capabilities
- See: [Web App Specification](planning/thingpress-web-app-spec.md)
- **Priority:** Medium-High - transforms user experience paradigm

### v2.1.0 - Security Enhancement
**IoT Permissions Analysis and Visualization**
- Analyze effective permissions from Thing Type + Thing Group + Policy combinations
- Visual permission matrix and conflict detection
- Real-time analysis as users configure settings
- Helps users understand security implications before deployment
- **Priority:** High within v2.x series - critical security and usability feature

### v3.0.0 - Protocol Expansion (Major Release)
**RFC 7030 EST Provisioning Integration**
- Implement Enrollment over Secure Transport (EST) protocol
- Support dynamic certificate provisioning alongside manifest import
- PKI integration and certificate authority connectivity
- Transforms Thingpress from import tool to comprehensive provisioning platform
- **Priority:** Medium - significant architectural expansion

## Research and Exploration

### Rust Transformation Analysis
**Performance Investigation (Branch: `rust-transformation`)**
- Evaluate Rust implementation for performance improvements
- Analyze Lambda cold start times and memory efficiency
- Compare development velocity and maintenance implications
- **Status:** Parallel research track - no version assigned pending feasibility results

## Future Development Areas

### Security & Compliance
- Enhanced credential rotation mechanisms
- Audit logging improvements
- Compliance reporting features

### Performance & Scalability
- Advanced throttling algorithms
- Multi-region deployment support
- Performance monitoring and alerting

### Vendor Support
- Additional hardware vendor integrations
- Enhanced certificate validation
- Vendor-specific optimization features

### Developer Experience
- Improved documentation and examples
- Enhanced debugging and troubleshooting tools
- Streamlined deployment processes

### Monitoring & Operations
- Enhanced CloudWatch integration
- Operational dashboards
- Automated health checks

## Detailed Roadmaps

- [Integration Test Status and Action Plan](planning/integration-test-status-and-action-plan.md)
- [Azure Migration Planning](planning/azure-migration.md)
- [Web App Specification](planning/thingpress-web-app-spec.md)

*Additional detailed roadmaps will be linked here as they are created in the planning/ directory.*

---

For questions about the roadmap or to propose new initiatives, please create an issue or discussion in the project repository.

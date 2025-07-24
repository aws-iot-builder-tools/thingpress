# Thingpress Versioning Scheme

Thingpress follows [Semantic Versioning](https://semver.org/) using a three-field version format: **XX.YY.ZZ**

## Version Format: XX.YY.ZZ

### XX - Major Version
- **Incremented for:** Breaking changes that are not backward compatible
- **Examples:**
  - API changes that break existing integrations
  - Removal of deprecated features
  - Fundamental architecture changes
  - Changes requiring user migration or reconfiguration

### YY - Minor Version  
- **Incremented for:** New features and functionality that are backward compatible
- **Examples:**
  - New vendor support (additional hardware manufacturers)
  - New Lambda functions or services
  - Enhanced existing features
  - New configuration options
  - Performance improvements

### ZZ - Patch Version (Minor Enhancement)
- **Incremented for:** Bug fixes and minor enhancements that are backward compatible
- **Examples:**
  - Bug fixes and error corrections
  - Security patches
  - Documentation updates
  - Code quality improvements
  - Minor performance optimizations
  - Dependency updates

## Version Decision Guidelines

### When to increment Major Version (XX):
- Breaking changes to Lambda function signatures
- Changes to S3 bucket structure or naming
- Removal of supported vendor formats
- Changes requiring CloudFormation stack updates
- API contract changes

### When to increment Minor Version (YY):
- Adding support for new hardware vendors
- New optional configuration parameters
- New Lambda functions or services
- Enhanced monitoring or logging features
- New deployment options

### When to increment Patch Version (ZZ):
- Bug fixes in certificate processing
- Security vulnerability patches
- Documentation improvements
- Code refactoring without functional changes
- Dependency security updates
- Performance optimizations

## Release Process

1. **Version Planning:** Determine appropriate version increment based on changes
2. **Quality Gates:** Ensure all quality thresholds are met
3. **Testing:** Complete unit tests and end-to-end testing via GitHub Actions
4. **Release:** Create GitHub release with semantic version tag
5. **Documentation:** Update CHANGELOG.md with version details

## Current Version Status

- **Target:** v1.0.0 (First major release)
- **Requirements:** Code quality completion + end-to-end testing automation

---

For questions about versioning decisions, refer to this document and consider the impact of changes on backward compatibility and user experience.

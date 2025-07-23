# Thingpress Integration Test Framework

## 🎯 **Overview**

The Thingpress integration test framework provides comprehensive testing capabilities for the entire certificate processing pipeline. It includes both component-level and end-to-end testing strategies.

## 📁 **Framework Structure**

```
test/integration/
├── common/
│   └── test_framework.py          # Common utilities and base classes
├── component/                     # Component-level testing
│   ├── test_microchip_provider.py
│   ├── test_infineon_provider.py
│   ├── test_espressif_provider.py
│   └── test_generated_provider.py
├── end_to_end/                    # End-to-end testing
│   ├── e2e_test_framework.py      # E2E framework base
│   ├── test_microchip_e2e.py
│   ├── test_infineon_e2e.py
│   ├── test_espressif_e2e.py
│   └── test_generated_e2e.py
├── run_component_tests.py         # Component test runner
├── run_e2e_tests.py              # E2E test runner
├── manual_integration_test.py     # Manual testing script
└── quick_e2e_test.py             # Quick validation
```

## 🧪 **Test Types**

### **Component Tests**
- Test individual Lambda functions in isolation
- Mock external dependencies
- Validate function logic and error handling
- Fast execution (seconds)

**Usage:**
```bash
python test/integration/run_component_tests.py --provider microchip
python test/integration/run_component_tests.py --all
```

### **End-to-End Tests**
- Test complete workflows from S3 upload to IoT thing creation
- Use real AWS services
- Validate entire processing pipeline
- Slower execution (minutes)

**Usage:**
```bash
python test/integration/run_e2e_tests.py --providers microchip
python test/integration/run_e2e_tests.py --all
```

### **Manual Tests**
- Interactive testing with real manifests
- Helpful for debugging and validation
- Provides detailed feedback

**Usage:**
```bash
python test/integration/manual_integration_test.py
python test/integration/quick_e2e_test.py
```

## 🔧 **Configuration**

### **Environment Variables**
```bash
# Required for some tests
export POWERTOOLS_IDEMPOTENCY_TABLE=test-table
export AWS_DEFAULT_REGION=us-east-1
```

### **AWS Credentials**
Tests require valid AWS credentials with permissions for:
- Lambda function invocation
- S3 bucket access
- IoT service operations
- SQS queue operations
- CloudFormation stack description

## 📊 **Test Coverage**

### **Providers Covered**
- ✅ **Microchip**: JSON manifests
- ✅ **Infineon**: 7z archives  
- ✅ **Espressif**: CSV manifests
- ✅ **Generated**: TXT files

### **Test Scenarios**
- Valid manifest processing
- Invalid manifest handling
- Error conditions and recovery
- Idempotency verification
- Performance under load

## 🚨 **Known Issues**

### **Layer Dependency Issue**
**Status**: BLOCKING  
**Impact**: All provider functions fail with `ModuleNotFoundError: No module named 'aws_utils'`  
**Workaround**: Use manual testing to verify S3 upload functionality  
**Reference**: See `LAYER_DEPENDENCY_REFERENCE.md`

### **Import Compatibility**
**Status**: ✅ RESOLVED  
**Solution**: Robust multi-fallback import strategy implemented  
**Coverage**: All provider functions support both unit test and Lambda environments

## 🎯 **Best Practices**

### **Running Tests**
1. **Start with quick validation**: `quick_e2e_test.py`
2. **Run component tests**: Fast feedback on logic
3. **Run E2E tests**: Validate complete workflows
4. **Use manual tests**: For debugging specific issues

### **Test Development**
1. **Follow naming conventions**: `test_<provider>_<scenario>.py`
2. **Use common framework**: Extend base classes from `test_framework.py`
3. **Clean up resources**: Always cleanup test artifacts
4. **Document test scenarios**: Clear descriptions of what's being tested

### **Debugging**
1. **Check logs**: CloudWatch logs for Lambda functions
2. **Verify resources**: Ensure all AWS resources are deployed
3. **Test incrementally**: Start with simple scenarios
4. **Use debug scripts**: Available in `scripts/debug/`

## 📈 **Future Enhancements**

- **Performance testing**: Load testing with large manifests
- **Chaos engineering**: Failure injection and recovery testing
- **Monitoring integration**: CloudWatch metrics and alarms
- **CI/CD integration**: Automated testing in pipelines
- **Test data management**: Standardized test datasets

## 🔗 **Related Documentation**

- `INTEGRATION_TEST_FINDINGS.md`: Session findings and technical debt resolution
- `LAYER_DEPENDENCY_REFERENCE.md`: Layer dependency troubleshooting
- `../troubleshooting/import-issues-resolved.md`: Import fix documentation

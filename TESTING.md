# Thingpress Testing Guide

This document provides an overview of the testing infrastructure for Thingpress.

## 📁 Testing Directory Structure

```
test/
├── unit/                    # Unit tests
├── integration/             # Integration tests
│   ├── end_to_end/         # E2E test implementations
│   ├── run_e2e_tests.py    # E2E test runner
│   └── quick_e2e_test.py   # Quick E2E validation
└── performance/             # Performance tests
    ├── performance_test_integrated.py
    ├── run_performance_test.sh
    └── PERFORMANCE_TESTING.md
```

## 🧪 Test Types

### Unit Tests
Located in `test/unit/`
```bash
# Run all unit tests
python -m pytest test/unit/ -v

# Run specific test file
python -m pytest test/unit/src/test_aws_utils.py -v
```

### Integration Tests
Located in `test/integration/`
```bash
# Run E2E tests
cd test/integration
python run_e2e_tests.py

# Quick E2E validation
python quick_e2e_test.py
```

### Performance Tests
Located in `test/performance/`
```bash
# Navigate to performance test directory
cd test/performance

# Run small scale test (5,000 certificates)
./run_performance_test.sh --scale small

# Run custom test
./run_performance_test.sh --certificates 25000
```

## 📊 Performance Testing

For detailed performance testing documentation, see:
- [`test/performance/PERFORMANCE_TESTING.md`](test/performance/PERFORMANCE_TESTING.md)

### Quick Performance Test
```bash
cd test/performance
./run_performance_test.sh --scale medium
```

This will:
- Generate 25,000 certificates on-demand
- Upload them in optimal 1,000-certificate batches
- Validate end-to-end processing performance
- Clean up all temporary files automatically

## 🎯 Test Coverage

- **Unit Tests**: Core functionality validation
- **Integration Tests**: End-to-end provider testing
- **Performance Tests**: Scale validation up to 200K certificates

## 🔧 Test Configuration

Test configuration files:
- `pytest.ini` - Pytest configuration
- `test/conftest.py` - Shared test fixtures
- `.coverage` - Coverage reporting configuration

## 📈 Continuous Integration

All tests are designed to run in CI/CD environments:
- Unit tests run on every commit
- Integration tests validate provider functionality
- Performance tests validate scale capabilities

For more details on specific test types, see the documentation in each test directory.

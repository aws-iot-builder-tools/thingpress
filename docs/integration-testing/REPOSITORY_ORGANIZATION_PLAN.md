# Repository Organization Plan

## 🎯 **Integration Testing Sources to Commit**

### **New Integration Test Framework (test/integration/)**
```
test/integration/
├── __init__.py                           # ✅ NEW - Package init
├── common/
│   ├── __init__.py                       # ✅ NEW - Package init  
│   └── test_framework.py                 # ✅ NEW - Common test utilities
├── component/
│   ├── __init__.py                       # ✅ NEW - Package init
│   ├── test_microchip_provider.py        # ✅ NEW - Microchip component tests
│   ├── test_infineon_provider.py         # ✅ NEW - Infineon component tests
│   ├── test_espressif_provider.py        # ✅ NEW - Espressif component tests
│   └── test_generated_provider.py        # ✅ NEW - Generated component tests
├── end_to_end/
│   ├── __init__.py                       # ✅ NEW - Package init
│   ├── e2e_test_framework.py             # ✅ NEW - E2E test framework
│   ├── test_microchip_e2e.py             # ✅ NEW - Microchip E2E tests
│   ├── test_infineon_e2e.py              # ✅ NEW - Infineon E2E tests
│   ├── test_espressif_e2e.py             # ✅ NEW - Espressif E2E tests
│   └── test_generated_e2e.py             # ✅ NEW - Generated E2E tests
├── run_component_tests.py                # ✅ NEW - Component test runner
├── run_e2e_tests.py                      # ✅ NEW - E2E test runner
├── manual_integration_test.py            # ✅ NEW - Manual test script
└── quick_e2e_test.py                     # ✅ NEW - Quick validation script
```

### **Documentation to Commit**
```
docs/
├── integration-testing/
│   ├── INTEGRATION_TEST_FINDINGS.md     # ✅ NEW - Session findings
│   ├── LAYER_DEPENDENCY_REFERENCE.md   # ✅ NEW - Layer issue reference
│   └── integration-test-framework.md    # ✅ NEW - Framework documentation
└── troubleshooting/
    └── import-issues-resolved.md         # ✅ NEW - Import fixes documentation
```

### **Scripts to Organize**
```
scripts/
├── debug/
│   ├── debug_microchip_test.py          # ✅ MOVE from root
│   └── test_lambda_import.py             # ✅ MOVE from root
└── integration/
    └── run_integration_tests.py          # ✅ MOVE from script/
```

## 🗂️ **Files to Move/Organize**

### **Root Directory Cleanup**
**Files to MOVE:**
- `debug_microchip_test.py` → `scripts/debug/`
- `test_lambda_import.py` → `scripts/debug/`
- `INTEGRATION_TEST_FINDINGS.md` → `docs/integration-testing/`
- `LAYER_DEPENDENCY_REFERENCE.md` → `docs/integration-testing/`
- `convo.md` → `docs/session-logs/` (if keeping)

**Files to KEEP in root:**
- `README.md`
- `CODE_OF_CONDUCT.md`
- `CONTRIBUTING.md`

### **Existing Files to Organize**
**Already in correct locations:**
- `test/integration/` - ✅ Properly organized
- `test/unit/` - ✅ Already organized
- `test/artifacts/` - ✅ Already organized

## 📋 **Git Commit Strategy**

### **Commit 1: Create directory structure**
```bash
mkdir -p docs/integration-testing
mkdir -p docs/troubleshooting  
mkdir -p scripts/debug
mkdir -p scripts/integration
mkdir -p test/integration/common
mkdir -p test/integration/component
mkdir -p test/integration/end_to_end
```

### **Commit 2: Add integration test framework**
```bash
git add test/integration/
git commit -m "feat: Add comprehensive integration test framework

- Component testing framework for individual provider functions
- End-to-end testing framework for complete workflows
- Test runners for automated execution
- Manual testing scripts for validation
- Covers all 4 providers: Microchip, Infineon, Espressif, Generated"
```

### **Commit 3: Move and organize scripts**
```bash
git mv debug_microchip_test.py scripts/debug/
git mv test_lambda_import.py scripts/debug/
git mv script/run_integration_tests.py scripts/integration/
git commit -m "refactor: Organize debug and integration scripts

- Move debug scripts to scripts/debug/
- Move integration scripts to scripts/integration/
- Clean up root directory structure"
```

### **Commit 4: Add documentation**
```bash
git mv INTEGRATION_TEST_FINDINGS.md docs/integration-testing/
git mv LAYER_DEPENDENCY_REFERENCE.md docs/integration-testing/
git add docs/
git commit -m "docs: Add integration testing documentation

- Session findings and technical debt resolution
- Layer dependency issue reference and troubleshooting
- Import fixes documentation"
```

### **Commit 5: Update import fixes**
```bash
git add src/provider_microchip/provider_microchip/main.py
git add src/provider_infineon/provider_infineon/main.py
git commit -m "fix: Resolve provider import compatibility issues

- Add robust multi-fallback import strategy
- Support both unit test and Lambda environments
- Eliminate relative import technical debt
- Ensure compatibility across deployment contexts"
```

## 🎯 **Priority Order**

1. **HIGH**: Integration test framework (test/integration/)
2. **HIGH**: Import fixes (src/provider_*/main.py)
3. **MEDIUM**: Documentation (docs/)
4. **MEDIUM**: Script organization (scripts/)
5. **LOW**: Root directory cleanup

## ✅ **Verification Checklist**

- [ ] All integration test files committed
- [ ] Import fixes committed  
- [ ] Documentation organized and committed
- [ ] Scripts moved to appropriate directories
- [ ] Root directory cleaned up
- [ ] All __init__.py files added for Python packages
- [ ] Git history preserves file origins where possible
- [ ] README updated to reference new structure (if needed)

## 🚨 **Important Notes**

1. **Layer Dependency Issue**: Document but don't commit broken code
2. **Test Artifacts**: Keep test/artifacts/ as-is (already organized)
3. **Build Artifacts**: Never commit .aws-sam/build/ contents
4. **Session Logs**: Consider if convo.md should be committed or archived
5. **Import Fixes**: These are working and should be committed immediately

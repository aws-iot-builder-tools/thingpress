# Pylint Cleanup Plan

**Current Score:** 7.61/10  
**Total Issues:** 57  
**Target Score:** 9.0+ (industry standard for production code)

## Issue Breakdown

### 🔴 CRITICAL (Must Fix) - 1 issue
- **syntax-error (1)**: `src/provider_generated/main.py:136` - Parsing failed due to illegal annotation target

### 🟡 HIGH PRIORITY (Easy wins) - 32 issues  
**CONVENTION Issues:**
- **trailing-whitespace (17)**: Remove trailing spaces from lines
- **line-too-long (9)**: Break lines longer than 100 characters
- **trailing-newlines (2)**: Remove extra newlines at end of files
- **import-outside-toplevel (2)**: Move imports to top of file
- **wrong-import-order (2)**: Reorder imports (stdlib, third-party, local)

### 🟠 MEDIUM PRIORITY (Code quality) - 20 issues
**WARNING Issues:**
- **unused-import (8)**: Remove unused import statements
- **unused-argument (3)**: Add underscore prefix or use argument
- **logging-fstring-interpolation (3)**: Use lazy % formatting in logging
- **fixme (2)**: Address TODO comments
- **redefined-outer-name (2)**: Rename variables to avoid shadowing
- **reimported (2)**: Remove duplicate imports

### 🟢 LOW PRIORITY (Refactoring) - 4 issues
**REFACTOR Issues:**
- **duplicate-code (4)**: Extract common code into shared functions

## Implementation Strategy

### Phase 1: Critical Fixes (Target: 8.5+ score)
1. **Fix syntax error** in `src/provider_generated/main.py:136`
2. **Clean whitespace issues** (trailing whitespace, newlines)
3. **Fix import issues** (order, duplicates, unused)
4. **Break long lines**

### Phase 2: Code Quality (Target: 9.0+ score)  
1. **Fix logging issues** (use lazy formatting)
2. **Handle unused arguments** (prefix with underscore)
3. **Address TODO comments**
4. **Fix variable shadowing**

### Phase 3: Refactoring (Target: 9.5+ score)
1. **Extract duplicate code** into shared utilities
2. **Review and optimize** remaining issues

## Automated Fixes Available

Many issues can be fixed automatically:
- **autopep8** for whitespace and line length
- **isort** for import ordering  
- **Manual regex** for trailing whitespace

## Files Requiring Attention

### High Impact Files:
1. `src/provider_generated/main.py` - Syntax error + multiple issues
2. `src/provider_generated/provider_generated/main.py` - Import issues
3. `src/provider_espressif/main.py` - Import issues  
4. `src/bulk_importer/main.py` - Line length + TODO
5. `src/product_verifier/main.py` - Logging issues + TODO

### Quick Win Files:
- `src/provider_generated/__init__.py` - Just trailing newlines
- `src/provider_generated/provider_generated/__init__.py` - Just trailing newlines

## Expected Score Improvements

- **Phase 1 completion**: 8.5-9.0 score
- **Phase 2 completion**: 9.0-9.5 score  
- **Phase 3 completion**: 9.5+ score

## Implementation Commands

```bash
# Phase 1: Automated fixes
autopep8 --in-place --max-line-length=100 src/
isort src/
find src/ -name "*.py" -exec sed -i 's/[[:space:]]*$//' {} \;

# Phase 2: Manual fixes required
# - Fix syntax error in provider_generated/main.py
# - Address unused arguments and imports
# - Fix logging statements

# Phase 3: Refactoring
# - Extract common patterns
# - Optimize duplicate code
```

This plan prioritizes fixes that will have the biggest impact on the pylint score while maintaining code functionality.

# AWS Session Management for Integration Testing

## 🚨 **Problem: Token Expiration During Tests**

Integration tests fail with `ExpiredTokenException` because:
- **Current Setup**: Using assumed role credentials (1-hour limit)
- **Test Duration**: Integration tests can take 5-15 minutes
- **Multiple Tests**: Running multiple tests exceeds 1-hour limit

## 🔍 **Current Identity Analysis**

```bash
# Check current identity
aws sts get-caller-identity
# Result: arn:aws:sts::517295686160:assumed-role/Admin/elberger-Isengard
```

**Limitations of Assumed Role Credentials:**
- ✅ Cannot call `GetSessionToken` 
- ✅ Maximum 1-hour duration
- ✅ Cannot be extended programmatically

## 🛠️ **Solutions**

### **Solution 1: Use IAM User Credentials (Recommended)**

If you have IAM user credentials available:

```bash
# Configure AWS CLI with IAM user credentials
aws configure --profile long-session
# Enter IAM user access key and secret key

# Use the profile for testing
export AWS_PROFILE=long-session

# Run integration tests
python test/integration/manual_integration_test.py
```

**Benefits:**
- ✅ Can request up to 12-hour sessions
- ✅ Can use `GetSessionToken` for extended duration
- ✅ More suitable for long-running tests

### **Solution 2: Modify Assume Role Duration**

If you must use assumed roles, configure longer duration:

```bash
# In ~/.aws/config
[profile long-duration]
role_arn = arn:aws:iam::517295686160:role/Admin
source_profile = default
duration_seconds = 14400  # 4 hours (max for most roles)
```

**Usage:**
```bash
export AWS_PROFILE=long-duration
python test/integration/manual_integration_test.py
```

### **Solution 3: Test Session Management (Implemented)**

Use the session manager for automatic refresh:

```python
from test.integration.common.session_manager import get_extended_client

# Use extended client instead of boto3.client()
iot_client = get_extended_client('iot')
s3_client = get_extended_client('s3')
```

### **Solution 4: Quick Tests (Implemented)**

Run shorter tests that complete within token limits:

```bash
# Quick tagging test (< 2 minutes)
python test/integration/quick_tagging_test.py

# Quick E2E validation (< 1 minute)  
python test/integration/quick_e2e_test.py
```

## 🎯 **Recommended Approach**

### **For Development/Testing:**
1. **Use Quick Tests**: Run `quick_tagging_test.py` for immediate feedback
2. **Session Manager**: Use extended session manager for longer tests
3. **Batch Testing**: Run multiple short tests instead of one long test

### **For CI/CD:**
1. **IAM User**: Use IAM user credentials with extended sessions
2. **Service Role**: Use service-linked roles with appropriate duration
3. **Refresh Logic**: Implement token refresh in test framework

## 🔧 **Implementation Examples**

### **Extended Session Script**
```bash
# Generate extended session credentials
python scripts/debug/configure_extended_session.py

# Source the generated credentials
source .env.extended

# Run tests with extended session
python test/integration/manual_integration_test.py
```

### **Session Manager Usage**
```python
from test.integration.common.session_manager import ExtendedSessionManager

# Create session manager with 2-hour duration
session_manager = ExtendedSessionManager(duration_hours=2)

# Get clients that auto-refresh
iot_client = session_manager.get_client('iot')
s3_client = session_manager.get_client('s3')

# Session automatically refreshes when needed
```

## 📊 **Token Duration Limits**

| Credential Type | Max Duration | GetSessionToken | Notes |
|----------------|--------------|-----------------|-------|
| IAM User | 12 hours | ✅ Yes | Best for testing |
| Assumed Role | 1-12 hours* | ❌ No | Depends on role config |
| Federated User | 12 hours | ✅ Yes | If available |
| EC2 Instance Profile | 6 hours | ❌ No | Auto-refresh |

*Most assumed roles default to 1 hour

## 🚀 **Quick Start**

For immediate testing with current setup:

```bash
# 1. Run quick test (completes in < 2 minutes)
python test/integration/quick_tagging_test.py

# 2. If you need longer tests, use session manager
python -c "
from test.integration.common.session_manager import get_session_manager
manager = get_session_manager(duration_hours=1)
print(f'Session expires in: {manager.time_until_expiry()}')
"

# 3. For production testing, configure IAM user profile
aws configure --profile testing
export AWS_PROFILE=testing
```

## 🔍 **Troubleshooting**

### **"Cannot call GetSessionToken with session credentials"**
- You're using assumed role credentials
- Switch to IAM user credentials or use session manager

### **"ExpiredTokenException"**
- Token expired during test execution
- Use shorter tests or session manager with auto-refresh

### **"AccessDenied"**
- Insufficient permissions for GetSessionToken
- Check IAM policies or use different credential type

## 📋 **Next Steps**

1. **Immediate**: Use `quick_tagging_test.py` to verify tagging works
2. **Short-term**: Implement session manager in existing tests  
3. **Long-term**: Configure IAM user credentials for extended testing

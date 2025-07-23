# 🚨 CRITICAL: Provider Layer Dependency Issue

## **Quick Reference**

**Issue**: All provider functions fail with `ModuleNotFoundError: No module named 'aws_utils'`  
**Root Cause**: ThingpressUtilsLayer not properly accessible to provider functions  
**Impact**: Complete blockage of certificate processing pipeline  

## **Provider Dependencies on Layer**

### **All Providers Import from Layer:**
```python
# Microchip & Espressif & Generated
from aws_utils import s3_object_bytes, send_sqs_message

# Infineon  
from aws_utils import verify_queue, boto_exception

# Certificate utilities (all providers)
from cert_utils import get_cn  # (some providers)
```

### **Layer Structure Expected:**
```
ThingpressUtilsLayer/
├── aws_utils.py          # ❌ MISSING or not accessible
├── cert_utils.py         # Probably also affected
└── other utilities...
```

## **Diagnostic Commands**

### **Check Layer Deployment:**
```bash
# List layers
aws lambda list-layers

# Get layer details  
aws lambda get-layer-version \
  --layer-name ThingpressUtilsLayer \
  --version-number 1

# Check function layer attachment
aws lambda get-function \
  --function-name sam-app-ThingpressMicrochipProviderFunction-YQ9VEQyIbh3H
```

### **Verify Layer Contents:**
```bash
# Check what's in the built layer
ls -la .aws-sam/build/ThingpressUtilsLayer/

# Look for aws_utils
find .aws-sam/build/ThingpressUtilsLayer/ -name "*aws_utils*"
```

## **Quick Test:**
```bash
# Test layer import directly
cd .aws-sam/build/ThingpressUtilsLayer/
python -c "import aws_utils; print('Layer import works')"
```

## **Template Configuration to Check:**
```yaml
# In template.yaml - verify layer is properly defined and attached
ThingpressUtilsLayer:
  Type: AWS::Serverless::LayerVersion
  Properties:
    LayerName: ThingpressUtilsLayer
    ContentUri: src/layer_utils/
    # ... other properties

# Provider functions should have:
Layers:
  - !Ref ThingpressUtilsLayer
```

---
**Status**: Import technical debt ✅ RESOLVED | Layer dependency ❌ NEEDS INVESTIGATION

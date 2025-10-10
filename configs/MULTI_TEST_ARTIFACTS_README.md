# Multi-Attachment Test Artifacts - Quick Reference

## Files

**Policies (3):**
- `multi-test-policy-base.json` - Base connectivity
- `multi-test-policy-sensor.json` - Sensor telemetry
- `multi-test-policy-admin.json` - Admin operations

**Thing Groups (3):**
- `multi-test-thing-group-dept.json` - Department: Engineering
- `multi-test-thing-group-location.json` - Location: Seattle
- `multi-test-thing-group-product.json` - Product: Sensor

**Scripts:**
- `../scripts/install-multi-test-artifacts.sh` - Install all resources
- `../scripts/uninstall-multi-test-artifacts.sh` - Remove all resources

**Documentation:**
- `multi-attachment-test-artifacts.md` - Full specification

## Quick Start

### Install Resources

```bash
cd /path/to/thingpress
./scripts/install-multi-test-artifacts.sh us-east-1
```

### Uninstall Resources

```bash
./scripts/uninstall-multi-test-artifacts.sh us-east-1
```

## Resources Created

| Type | Name | Purpose |
|------|------|---------|
| Policy | MultiTestBasePolicy | Base connectivity |
| Policy | MultiTestSensorPolicy | Sensor operations |
| Policy | MultiTestAdminPolicy | Admin operations |
| Thing Group | multi-test-dept-engineering | Department hierarchy |
| Thing Group | multi-test-location-seattle | Location hierarchy |
| Thing Group | multi-test-product-sensor | Product hierarchy |

## Test Configuration

Use in SAM config:

```toml
parameter_overrides = "IoTPolicies=\"MultiTestBasePolicy,MultiTestSensorPolicy,MultiTestAdminPolicy\" IoTThingGroups=\"multi-test-dept-engineering,multi-test-location-seattle,multi-test-product-sensor\" ..."
```

## Cleanup

The uninstall script handles cleanup, but if manual cleanup is needed:

```bash
# Detach policies from certificates first
aws iot list-targets-for-policy --policy-name MultiTestBasePolicy
# Then detach each...

# Remove things from groups first
aws iot list-things-in-thing-group --thing-group-name multi-test-dept-engineering
# Then remove each...

# Then run uninstall script
./scripts/uninstall-multi-test-artifacts.sh
```

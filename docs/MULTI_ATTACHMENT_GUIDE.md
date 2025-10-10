# Multiple Policies and Thing Groups - Quick Reference

## Overview

Thingpress now supports attaching multiple policies, thing groups, and thing types to each certificate/thing. This enables enterprise IoT deployment patterns with hierarchical organization.

## Parameter Syntax

### New Multi-Value Parameters (Recommended)

Use comma-delimited lists for multiple values:

```bash
sam deploy --parameter-overrides \
  IoTPolicies=policy1,policy2,policy3 \
  IoTThingGroups=dept-eng,location-seattle,product-sensor \
  IoTThingTypes=temp-sensor,humidity-sensor
```

### Legacy Single-Value Parameters (Still Supported)

Existing single-value syntax continues to work:

```bash
sam deploy --parameter-overrides \
  IoTPolicy=my-policy \
  IoTThingGroup=my-group \
  IoTThingType=my-type
```

## Common Use Cases

### 1. Organizational Hierarchy

```bash
IoTThingGroups=company-acme,dept-engineering,team-iot,location-seattle
```

Creates a hierarchy:
- Company → Department → Team → Location

### 2. Layered Access Control

```bash
IoTPolicies=base-connectivity,role-sensor,location-restricted
```

Applies multiple policies:
- Base policy: Basic MQTT connectivity
- Role policy: Sensor-specific permissions
- Location policy: Regional restrictions

### 3. Device Categorization

```bash
IoTThingTypes=hardware-esp32,firmware-v2.1,capability-temperature
```

Multiple classifications:
- Hardware model
- Firmware version
- Device capabilities

### 4. Mixed Deployment

```bash
# Some devices with multiple policies
IoTPolicies=base-policy,admin-policy

# Other devices with single policy (legacy)
IoTPolicy=basic-policy
```

## Best Practices

### Policy Organization

1. **Base Policy**: Common permissions for all devices
   ```
   base-connectivity-policy
   ```

2. **Role Policies**: Device-type specific permissions
   ```
   role-sensor-policy, role-actuator-policy
   ```

3. **Location Policies**: Regional or facility restrictions
   ```
   location-us-west-policy, location-factory-a-policy
   ```

### Thing Group Hierarchy

Organize from general to specific:
```
company → division → department → location → product-line → model
```

Example:
```bash
IoTThingGroups=acme-corp,manufacturing,quality-control,seattle-plant,sensor-network,model-x100
```

### Thing Type Strategy

Use for device characteristics:
```bash
IoTThingTypes=hardware-esp32,sensor-temperature,protocol-mqtt
```

## Recommended Limits

- **Policies**: Maximum 5 per certificate
- **Thing Groups**: Maximum 10 per thing
- **Thing Types**: Maximum 3 per thing

Exceeding these limits may impact performance.

## Special Values

### None/Empty Values

To specify no attachments:
```bash
IoTPolicies=None
# or
IoTThingGroups=
```

Both are equivalent and result in no attachments.

### Filtering None in Lists

The system automatically filters out "None" values:
```bash
IoTPolicies=policy1,None,policy2
# Results in: policy1, policy2
```

## Migration from Legacy Parameters

### Step 1: Identify Current Configuration

```bash
# Current deployment
sam deploy --parameter-overrides \
  IoTPolicy=my-policy \
  IoTThingGroup=my-group
```

### Step 2: Convert to New Format

```bash
# New deployment (same behavior)
sam deploy --parameter-overrides \
  IoTPolicies=my-policy \
  IoTThingGroups=my-group
```

### Step 3: Add Additional Values

```bash
# Enhanced deployment
sam deploy --parameter-overrides \
  IoTPolicies=my-policy,additional-policy \
  IoTThingGroups=my-group,location-group,dept-group
```

## Troubleshooting

### Issue: Policies Not Attaching

**Check:**
1. Policy names are correct (case-sensitive)
2. Policies exist in AWS IoT Core
3. No extra spaces in comma-delimited list
4. CloudWatch logs for validation errors

### Issue: Thing Groups Not Working

**Check:**
1. Thing groups exist before deployment
2. Thing group names match exactly
3. Proper permissions in IAM role
4. Check Product Verifier logs

### Issue: Backward Compatibility

**If legacy parameters stop working:**
1. Verify both old and new parameters are in template
2. Check environment variable mappings
3. Ensure fallback logic in Product Verifier

## Examples by Industry

### Manufacturing

```bash
IoTPolicies=base-mqtt,manufacturing-floor,quality-control
IoTThingGroups=factory-seattle,line-assembly-1,zone-welding
IoTThingTypes=plc-controller,sensor-vibration
```

### Smart Buildings

```bash
IoTPolicies=base-connectivity,building-automation,hvac-control
IoTThingGroups=building-hq,floor-3,zone-west-wing
IoTThingTypes=thermostat,occupancy-sensor
```

### Fleet Management

```bash
IoTPolicies=base-telemetry,fleet-tracking,geofence-enabled
IoTThingGroups=fleet-delivery,region-west,vehicle-type-van
IoTThingTypes=gps-tracker,obd-reader
```

## API Reference

### Config Structure (Internal)

Product Verifier passes this structure to Bulk Importer:

```python
config = {
    'policies': [
        {'name': 'policy1', 'arn': 'arn:aws:iot:...'},
        {'name': 'policy2', 'arn': 'arn:aws:iot:...'}
    ],
    'thing_groups': [
        {'name': 'group1', 'arn': 'arn:aws:iot:...'},
        {'name': 'group2', 'arn': 'arn:aws:iot:...'}
    ],
    'thing_types': ['type1', 'type2']
}
```

### Backward Compatible Structure

Legacy single-value format still works:

```python
config = {
    'policy_name': 'my-policy',
    'thing_group_arn': 'arn:aws:iot:...',
    'thing_type_name': 'my-type'
}
```

## Support

For issues or questions:
1. Check CloudWatch logs for Product Verifier and Bulk Importer
2. Validate parameter syntax with `sam validate`
3. Review this guide for common patterns
4. Create an issue in the repository

## Version History

- **v1.0.1**: Added multiple policies, thing groups, and thing types support
- **v1.0.0**: Initial release with single-value parameters

#!/bin/bash
# Uninstall multi-attachment test artifacts (policies and thing groups)
# Usage: ./scripts/uninstall-multi-test-artifacts.sh [region]
# WARNING: This will delete all versions of the policies

set -e

REGION="${1:-us-east-1}"

echo "Uninstalling multi-attachment test artifacts in region: $REGION"
echo "================================================================"
echo "WARNING: This will delete policies and thing groups"
echo "Press Ctrl+C to cancel, or Enter to continue..."
read -r

# Delete policies (all versions)
echo ""
echo "Deleting IoT Policies..."

for POLICY in MultiTestBasePolicy MultiTestSensorPolicy MultiTestAdminPolicy; do
  echo "Processing $POLICY..."
  
  # Get all versions
  VERSIONS=$(aws iot list-policy-versions --region "$REGION" --policy-name "$POLICY" \
    --query 'policyVersions[?!isDefaultVersion].versionId' --output text 2>/dev/null || echo "")
  
  # Delete non-default versions
  for VERSION in $VERSIONS; do
    aws iot delete-policy-version --region "$REGION" --policy-name "$POLICY" --policy-version-id "$VERSION" \
      && echo "  ✓ Deleted version $VERSION" \
      || echo "  ✗ Failed to delete version $VERSION"
  done
  
  # Delete default version (policy itself)
  aws iot delete-policy --region "$REGION" --policy-name "$POLICY" \
    && echo "✓ Deleted $POLICY" \
    || echo "✗ Failed to delete $POLICY (may not exist or still attached)"
done

# Delete thing groups
echo ""
echo "Deleting Thing Groups..."

for GROUP in multi-test-dept-engineering multi-test-location-seattle multi-test-product-sensor; do
  aws iot delete-thing-group --region "$REGION" --thing-group-name "$GROUP" \
    && echo "✓ Deleted $GROUP" \
    || echo "✗ Failed to delete $GROUP (may not exist or still has things)"
done

# Verify
echo ""
echo "Verifying deletion..."
echo ""
echo "Remaining Policies:"
aws iot list-policies --region "$REGION" --query 'policies[?contains(policyName, `MultiTest`)].policyName' --output table

echo ""
echo "Remaining Thing Groups:"
aws iot list-thing-groups --region "$REGION" --query 'thingGroups[?contains(groupName, `multi-test`)].groupName' --output table

echo ""
echo "================================================================"
echo "Uninstallation complete!"
echo ""
echo "NOTE: If deletion failed, ensure:"
echo "  - Policies are detached from all certificates"
echo "  - Thing groups have no member things"

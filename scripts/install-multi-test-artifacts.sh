#!/bin/bash
# Install multi-attachment test artifacts (policies and thing groups)
# Usage: ./scripts/install-multi-test-artifacts.sh [region] [profile]

set -e

REGION="${1:-us-east-1}"
PROFILE="${2:-}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_DIR="$SCRIPT_DIR/../configs"

# Build AWS CLI profile flag
PROFILE_FLAG=""
if [ -n "$PROFILE" ]; then
  PROFILE_FLAG="--profile $PROFILE"
  echo "Using AWS profile: $PROFILE"
fi

echo "Installing multi-attachment test artifacts in region: $REGION"
echo "================================================================"

# Create policies
echo ""
echo "Creating IoT Policies..."
aws iot create-policy \
  --region "$REGION" $PROFILE_FLAG \
  --policy-name MultiTestBasePolicy \
  --policy-document "file://$CONFIG_DIR/multi-test-policy-base.json" \
  && echo "✓ Created MultiTestBasePolicy" \
  || echo "✗ Failed to create MultiTestBasePolicy (may already exist)"

aws iot create-policy \
  --region "$REGION" $PROFILE_FLAG \
  --policy-name MultiTestSensorPolicy \
  --policy-document "file://$CONFIG_DIR/multi-test-policy-sensor.json" \
  && echo "✓ Created MultiTestSensorPolicy" \
  || echo "✗ Failed to create MultiTestSensorPolicy (may already exist)"

aws iot create-policy \
  --region "$REGION" $PROFILE_FLAG \
  --policy-name MultiTestAdminPolicy \
  --policy-document "file://$CONFIG_DIR/multi-test-policy-admin.json" \
  && echo "✓ Created MultiTestAdminPolicy" \
  || echo "✗ Failed to create MultiTestAdminPolicy (may already exist)"

# Create thing groups
echo ""
echo "Creating Thing Groups..."
aws iot create-thing-group \
  --region "$REGION" $PROFILE_FLAG \
  --cli-input-json "file://$CONFIG_DIR/multi-test-thing-group-dept.json" \
  && echo "✓ Created multi-test-dept-engineering" \
  || echo "✗ Failed to create multi-test-dept-engineering (may already exist)"

aws iot create-thing-group \
  --region "$REGION" $PROFILE_FLAG \
  --cli-input-json "file://$CONFIG_DIR/multi-test-thing-group-location.json" \
  && echo "✓ Created multi-test-location-seattle" \
  || echo "✗ Failed to create multi-test-location-seattle (may already exist)"

aws iot create-thing-group \
  --region "$REGION" $PROFILE_FLAG \
  --cli-input-json "file://$CONFIG_DIR/multi-test-thing-group-product.json" \
  && echo "✓ Created multi-test-product-sensor" \
  || echo "✗ Failed to create multi-test-product-sensor (may already exist)"

# Verify
echo ""
echo "Verifying installation..."
echo ""
echo "Policies:"
aws iot list-policies --region "$REGION" $PROFILE_FLAG --query 'policies[?contains(policyName, `MultiTest`)].policyName' --output table

echo ""
echo "Thing Groups:"
aws iot list-thing-groups --region "$REGION" $PROFILE_FLAG --query 'thingGroups[?contains(groupName, `multi-test`)].groupName' --output table

echo ""
echo "================================================================"
echo "Installation complete!"

#!/bin/bash
# Script to create an IAM role for Thingpress deployment with GitHub OIDC

# Exit on error
set -e

# Check if required environment variables are set
if [ -z "$AWS_ACCOUNT_ID" ]; then
  echo "Error: AWS_ACCOUNT_ID environment variable is not set"
  exit 1
fi

if [ -z "$GITHUB_ORG" ]; then
  echo "Error: GITHUB_ORG environment variable is not set"
  exit 1
fi

if [ -z "$GITHUB_REPO" ]; then
  echo "Error: GITHUB_REPO environment variable is not set"
  exit 1
fi

# Set role name (can be overridden by environment variable)
ROLE_NAME="${THINGPRESS_ROLE_NAME:-ThingpressDeploymentRole}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Creating IAM role for Thingpress deployment..."
echo "Role name: $ROLE_NAME"

# Create a temporary copy of the trust policy to avoid modifying the original
TEMP_TRUST_POLICY=$(mktemp)
cp "$SCRIPT_DIR/thingpress-trust-policy.json" "$TEMP_TRUST_POLICY"

# Replace placeholders in the trust policy
sed -i "s/\${AWS_ACCOUNT_ID}/$AWS_ACCOUNT_ID/g" "$TEMP_TRUST_POLICY"
sed -i "s/\${GITHUB_ORG}/$GITHUB_ORG/g" "$TEMP_TRUST_POLICY"
sed -i "s/\${GITHUB_REPO}/$GITHUB_REPO/g" "$TEMP_TRUST_POLICY"

# Create the role with trust policy
echo "Creating IAM role with trust policy..."
aws iam create-role \
  --role-name "$ROLE_NAME" \
  --assume-role-policy-document "file://$TEMP_TRUST_POLICY"

# Attach the permissions policy
echo "Attaching permissions policy to the role..."
aws iam put-role-policy \
  --role-name "$ROLE_NAME" \
  --policy-name "ThingpressDeploymentPolicy" \
  --policy-document "file://$SCRIPT_DIR/thingpress-permissions-policy.json"

# Clean up temporary file
rm "$TEMP_TRUST_POLICY"

echo "IAM role '$ROLE_NAME' created successfully."
echo "Role ARN: arn:aws:iam::$AWS_ACCOUNT_ID:role/$ROLE_NAME"
echo ""
echo "Use this Role ARN in your GitHub Actions workflow."
echo "Example:"
echo "  role-to-assume: arn:aws:iam::$AWS_ACCOUNT_ID:role/$ROLE_NAME"

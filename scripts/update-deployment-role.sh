#!/bin/bash
# Update existing Thingpress deployment role with correct trust policy and permissions
# This script fixes the repository name and ensures all permissions are current

set -e

# Check required environment variables
if [ -z "$AWS_ACCOUNT_ID" ] || [ -z "$GITHUB_ORG" ] || [ -z "$GITHUB_REPO" ]; then
    echo "❌ Error: Required environment variables not set"
    echo "Please set:"
    echo "  export AWS_ACCOUNT_ID=\"your-account-id\""
    echo "  export GITHUB_ORG=\"your-github-org\""
    echo "  export GITHUB_REPO=\"your-repo-name\""
    echo ""
    echo "Example:"
    echo "  export AWS_ACCOUNT_ID=\"477252478758\""
    echo "  export GITHUB_ORG=\"aws-iot-builder-tools\""
    echo "  export GITHUB_REPO=\"thingpress\""
    exit 1
fi

# Set role name (can be overridden by environment variable)
ROLE_NAME="${THINGPRESS_ROLE_NAME:-ThingpressDeploymentRole}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "🔧 Updating Thingpress deployment role..."
echo "================================================"
echo "AWS Account ID: $AWS_ACCOUNT_ID"
echo "GitHub Org: $GITHUB_ORG"
echo "GitHub Repo: $GITHUB_REPO"
echo "Role Name: $ROLE_NAME"
echo "================================================"

# Check if role exists
echo "🔍 Checking if role exists..."
if ! aws iam get-role --role-name "$ROLE_NAME" >/dev/null 2>&1; then
    echo "❌ Role '$ROLE_NAME' does not exist. Please run create-deployment-role.sh first."
    exit 1
fi

echo "✅ Role '$ROLE_NAME' exists"

# Create a temporary copy of the trust policy to avoid modifying the original
TEMP_TRUST_POLICY=$(mktemp)
cp "$SCRIPT_DIR/thingpress-trust-policy.json" "$TEMP_TRUST_POLICY"

# Replace placeholders in the trust policy
echo "📝 Updating trust policy with current values..."
sed -i "s/\${AWS_ACCOUNT_ID}/$AWS_ACCOUNT_ID/g" "$TEMP_TRUST_POLICY"
sed -i "s/\${GITHUB_ORG}/$GITHUB_ORG/g" "$TEMP_TRUST_POLICY"
sed -i "s/\${GITHUB_REPO}/$GITHUB_REPO/g" "$TEMP_TRUST_POLICY"

# Update the role trust policy
echo "🔐 Updating role trust policy..."
aws iam update-assume-role-policy \
  --role-name "$ROLE_NAME" \
  --policy-document "file://$TEMP_TRUST_POLICY"

echo "✅ Trust policy updated successfully"

# Update the permissions policy
echo "🛡️ Updating permissions policy..."
aws iam put-role-policy \
  --role-name "$ROLE_NAME" \
  --policy-name "ThingpressDeploymentPolicy" \
  --policy-document "file://$SCRIPT_DIR/thingpress-permissions-policy.json"

echo "✅ Permissions policy updated successfully"

# Clean up temporary file
rm "$TEMP_TRUST_POLICY"

# Verify the role configuration
echo "🔍 Verifying role configuration..."
ROLE_ARN=$(aws iam get-role --role-name "$ROLE_NAME" --query 'Role.Arn' --output text)
echo "✅ Role ARN: $ROLE_ARN"

# Show trust policy summary
echo "📋 Trust policy summary:"
aws iam get-role --role-name "$ROLE_NAME" --query 'Role.AssumeRolePolicyDocument.Statement[0].Condition.StringLike' --output table

echo ""
echo "🎉 Role update completed successfully!"
echo "================================================"
echo "✅ Trust policy updated with correct repository: $GITHUB_ORG/$GITHUB_REPO"
echo "✅ Permissions policy updated with latest permissions"
echo "✅ Role is ready for GitHub Actions OIDC authentication"
echo ""
echo "Next steps:"
echo "1. Ensure GitHub repository secrets are configured:"
echo "   - AWS_ACCOUNT_ID: $AWS_ACCOUNT_ID"
echo "   - AWS_REGION: your-preferred-region"
echo "2. Test the GitHub Actions workflow"
echo "================================================"

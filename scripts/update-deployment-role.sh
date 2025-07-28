#!/bin/bash
# Script to update the existing IAM role for Thingpress deployment with enhanced permissions

# Exit on error
set -e

# Set role name (can be overridden by environment variable)
ROLE_NAME="${THINGPRESS_ROLE_NAME:-ThingpressDeploymentRole}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Updating IAM role permissions for Thingpress deployment..."
echo "Role name: $ROLE_NAME"

# Check if role exists
if ! aws iam get-role --role-name "$ROLE_NAME" >/dev/null 2>&1; then
  echo "Error: IAM role '$ROLE_NAME' does not exist."
  echo "Please run create-deployment-role.sh first to create the role."
  exit 1
fi

# Update the permissions policy
echo "Updating permissions policy for the role..."
aws iam put-role-policy \
  --role-name "$ROLE_NAME" \
  --policy-name "ThingpressDeploymentPolicy" \
  --policy-document "file://$SCRIPT_DIR/thingpress-permissions-policy.json"

echo "IAM role '$ROLE_NAME' permissions updated successfully."
echo ""
echo "The role now includes enhanced permissions for:"
echo "  - Lambda event source mapping management"
echo "  - CloudWatch dashboard deletion"
echo "  - Enhanced IAM role and policy management"
echo "  - Improved CloudFormation stack operations"
echo ""
echo "These changes will enable automatic stack deletion from GitHub workflows."

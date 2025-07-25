#!/bin/bash
# Quick fix script for GitHub OIDC authentication issue
# Sets the correct repository name and updates the deployment role

set -e

echo "🔧 Fixing GitHub OIDC authentication for Thingpress..."
echo "================================================"

# Set the correct values for your repository
export AWS_ACCOUNT_ID="477252478758"
export GITHUB_ORG="aws-iot-builder-tools"
export GITHUB_REPO="thingpress"

echo "Using repository: $GITHUB_ORG/$GITHUB_REPO"
echo "AWS Account: $AWS_ACCOUNT_ID"
echo ""

# Run the update script
./scripts/update-deployment-role.sh

echo ""
echo "🎉 GitHub OIDC fix completed!"
echo "You can now re-run your GitHub Actions workflow."

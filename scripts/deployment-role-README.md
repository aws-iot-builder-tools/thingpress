# Thingpress Deployment Role Setup

This directory contains scripts and configuration files to set up an IAM role for deploying Thingpress using GitHub Actions with OIDC authentication.

## Files

- `thingpress-permissions-policy.json`: IAM permissions policy that grants the necessary permissions to deploy Thingpress
- `thingpress-trust-policy.json`: IAM trust policy for GitHub OIDC authentication
- `create-deployment-role.sh`: Bash script to create the IAM role
- `update-deployment-role.sh`: Bash script to update an existing IAM role with enhanced permissions
- `github-workflow-example.yml`: Example GitHub Actions workflow file

## Prerequisites

1. AWS CLI installed and configured with administrator access
2. GitHub repository where you want to deploy Thingpress from
3. GitHub OIDC provider configured in your AWS account

## Setting up the GitHub OIDC Provider

If you haven't already set up the GitHub OIDC provider in your AWS account, run the following command:

```bash
aws iam create-open-id-connect-provider \
  --url https://token.actions.githubusercontent.com \
  --client-id-list sts.amazonaws.com \
  --thumbprint-list 6938fd4d98bab03faadb97b34396831e3780aea1
```

## Updating an Existing Deployment Role

If you already have a deployment role created but need to update it with enhanced permissions (for example, to enable automatic stack deletion), you can use the update script:

```bash
export THINGPRESS_ROLE_NAME="ThingpressDeploymentRole"  # Optional: custom role name
./update-deployment-role.sh
```

The enhanced permissions include:
- **Lambda Event Source Mappings**: `lambda:CreateEventSourceMapping`, `lambda:DeleteEventSourceMapping`, `lambda:GetEventSourceMapping`, `lambda:UpdateEventSourceMapping`
- **CloudWatch Dashboard Management**: `cloudwatch:DeleteDashboards`, `cloudwatch:ListDashboards`
- **Enhanced IAM Management**: Role creation, deletion, policy attachment/detachment for Thingpress resources
- **Improved CloudFormation Operations**: Stack drift detection and enhanced stack management

These permissions are essential for:
- Automatic cleanup of Lambda event source mappings during stack deletion
- Proper deletion of CloudWatch dashboards created by Thingpress
- Complete stack deletion without manual intervention
- Enhanced error handling and recovery in CI/CD pipelines

## Creating the Deployment Role

1. Set the required environment variables:

```bash
export AWS_ACCOUNT_ID="123456789012"  # Your AWS account ID
export GITHUB_ORG="your-org"          # Your GitHub organization or username
export GITHUB_REPO="thingpress"       # Your GitHub repository name
export THINGPRESS_ROLE_NAME="ThingpressDeploymentRole"  # Optional: custom role name
```

2. Run the script:

```bash
./create-deployment-role.sh
```

The script will:
- Replace placeholders in the trust policy with your values
- Create the IAM role with the trust policy
- Attach the permissions policy to the role
- Use a temporary file to avoid modifying the original trust policy template

## Using the Role in GitHub Actions

1. Add the following secrets to your GitHub repository:
   - `AWS_ACCOUNT_ID`: Your AWS account ID (e.g., "123456789012")
   - `AWS_REGION`: Your preferred AWS region (e.g., "us-east-1")
   - Optionally, other Thingpress-specific secrets:
     - `IOT_POLICY`: Name of the IoT policy to use
     - `IOT_THING_GROUP`: Name of the IoT thing group to use
     - `IOT_THING_TYPE`: Name of the IoT thing type to use

2. The GitHub Actions workflows will automatically construct the role ARN using:
   ```
   arn:aws:iam::${{ secrets.AWS_ACCOUNT_ID }}:role/ThingpressDeploymentRole
   ```

3. Both manual and release integration tests can be triggered:
   - **Manual**: Use workflow_dispatch to test specific providers
   - **Release**: Automatically triggered on GitHub releases

## Security Considerations

- The IAM role has the minimum permissions required to deploy Thingpress
- The trust policy restricts access to only your GitHub repository
- The role uses OIDC for authentication, avoiding the need for long-term credentials

## Troubleshooting

If you encounter issues:

1. Verify that the GitHub OIDC provider is correctly set up in your AWS account
2. Check that the environment variables are correctly set before running the script
3. Ensure your GitHub repository has the necessary secrets configured
4. Verify that your GitHub Actions workflow has the required permissions (`id-token: write` and `contents: read`)

### Stack Deletion Issues

If you experience CloudFormation stack deletion failures with permission errors:

1. **Lambda Permission Errors**: Update the role with enhanced Lambda permissions using `./update-deployment-role.sh`
2. **CloudWatch Dashboard Errors**: The enhanced permissions include `cloudwatch:DeleteDashboards` to resolve this
3. **Event Source Mapping Errors**: Enhanced permissions include full event source mapping management
4. **Manual Cleanup**: If stack deletion still fails, you may need to manually delete retained resources:
   ```bash
   # Delete S3 bucket contents first
   aws s3 rm s3://bucket-name --recursive
   # Then retry stack deletion with retain-resources option
   aws cloudformation delete-stack --stack-name stack-name --retain-resources ResourceName1 ResourceName2
   ```

### Permission Verification

To verify the role has the correct permissions, you can check the attached policies:

```bash
aws iam list-role-policies --role-name ThingpressDeploymentRole
aws iam get-role-policy --role-name ThingpressDeploymentRole --policy-name ThingpressDeploymentPolicy
```

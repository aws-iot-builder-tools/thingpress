# Thingpress Deployment Role Setup

This directory contains scripts and configuration files to set up an IAM role for deploying Thingpress using GitHub Actions with OIDC authentication.

## Files

- `thingpress-permissions-policy.json`: IAM permissions policy that grants the necessary permissions to deploy Thingpress
- `thingpress-trust-policy.json`: IAM trust policy for GitHub OIDC authentication
- `create-deployment-role.sh`: Bash script to create the IAM role
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

## Creating the Deployment Role

1. Set the required environment variables:

```bash
export AWS_ACCOUNT_ID="123456789012"  # Your AWS account ID
export GITHUB_ORG="your-org"          # Your GitHub organization or username
export GITHUB_REPO="thingpress"       # Your GitHub repository name
```

2. Run the script:

```bash
./create-deployment-role.sh
```

The script will:
- Replace placeholders in the trust policy with your values
- Create the IAM role with the trust policy
- Attach the permissions policy to the role

## Using the Role in GitHub Actions

1. Add the following secrets to your GitHub repository:
   - `AWS_ACCOUNT_ID`: Your AWS account ID
   - `IAM_USER_ARN`: ARN of the IAM user (if required by your template)
   - `IOT_POLICY`: Name of the IoT policy to use
   - `IOT_THING_GROUP`: Name of the IoT thing group to use
   - `IOT_THING_TYPE`: Name of the IoT thing type to use

2. Create a GitHub Actions workflow file (`.github/workflows/deploy.yml`) using the example provided in `github-workflow-example.yml`.

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

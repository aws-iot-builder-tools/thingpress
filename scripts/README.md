# Thingpress Deployment Scripts

This directory contains scripts for deploying the Thingpress stack with Microchip verifier certificates.

## Deployment Process

The deployment process consists of the following steps:

1. Encode the Microchip verifier certificates as base64
2. Transform the CloudFormation template to include the encoded certificates
3. Deploy the stack using AWS SAM

## Usage

To deploy the stack, run the `deploy.sh` script with the following parameters:

```bash
./deploy.sh --stack-name <stack-name> [--profile <profile-name>] [--region <region>]
```

### Parameters

- `--stack-name`: (Required) Name of the CloudFormation stack to create or update
- `--profile`: (Optional) AWS profile to use for deployment
- `--region`: (Optional) AWS region to deploy to (default: us-east-1)

## Example

```bash
./deploy.sh --stack-name thingpress-dev --profile myprofile --region us-west-2
```

## How It Works

The deployment process works as follows:

1. The `encode_certificates.py` script reads the Microchip verifier certificates from the `test/artifacts/mchp_verifiers` directory and encodes them as base64
2. The `transform_template.py` script processes the CloudFormation template to include the encoded certificates
3. The `deploy.sh` script deploys the transformed template using AWS SAM

## Microchip Verifier Certificates

The Microchip verifier certificates are deployed to the Microchip S3 bucket as part of the CloudFormation stack deployment. The certificates are deployed before the S3 event notifications are configured, so they don't trigger any Lambda functions during deployment.

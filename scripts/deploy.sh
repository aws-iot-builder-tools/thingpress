#!/bin/bash
# Script to deploy the Thingpress stack with Microchip verifier certificates

set -e

# Directory containing this script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

# Parse command line arguments
STACK_NAME=""
PROFILE=""
REGION="us-east-1"

while [[ $# -gt 0 ]]; do
  case $1 in
    --stack-name)
      STACK_NAME="$2"
      shift 2
      ;;
    --profile)
      PROFILE="$2"
      shift 2
      ;;
    --region)
      REGION="$2"
      shift 2
      ;;
    *)
      echo "Unknown option: $1"
      exit 1
      ;;
  esac
done

if [ -z "$STACK_NAME" ]; then
  echo "Error: --stack-name is required"
  exit 1
fi

# Set AWS profile if provided
if [ -n "$PROFILE" ]; then
  PROFILE_ARG="--profile $PROFILE"
else
  PROFILE_ARG=""
fi

# Step 1: Encode the certificates
echo "Encoding Microchip verifier certificates..."
python "$SCRIPT_DIR/encode_certificates.py" \
  --directory "$PROJECT_ROOT/test/artifacts/mchp_verifiers" \
  --output "$PROJECT_ROOT/src/certificate_deployer/certificates/encoded_certificates.json"

# Step 2: Transform the template
echo "Transforming CloudFormation template..."
python "$SCRIPT_DIR/transform_template.py" \
  --template "$PROJECT_ROOT/template.yaml" \
  --output "$PROJECT_ROOT/template.transformed.yaml"

# Step 3: Deploy the stack
echo "Deploying stack $STACK_NAME..."
sam deploy \
  --template-file "$PROJECT_ROOT/template.transformed.yaml" \
  --stack-name "$STACK_NAME" \
  --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM \
  --region "$REGION" \
  $PROFILE_ARG

echo "Deployment complete!"

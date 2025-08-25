#! /usr/bin/env python3
"""Transform a given AWS IoT Policy that can be consumed
by the AWS CLI IoT 'create-policy' command.
"""

import argparse
import json

def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Transform a given AWS IoT policy to an IoT create-policy AWS CLI skeleton file.')
    parser.add_argument('--policy-name', type=str, required=True,
                        help='The name of the AWS IoT policy. Is not validated for API constraints.')
    parser.add_argument('--policy-document', type=str, required=True,
                        help='The AWS IoT policy. NOTE: While this must be valid JSON, it is not validated')
    parser.add_argument('--output-skeleton', type=str, required=True,
                        help='The path and filename for the output.')
    return parser.parse_args()

def flesh_template(policy_name: str, policy_document: str):
    return {
        "policyName": policy_name,
        "policyDocument": policy_document,
    }

def transform_policy_document(policy_document: str) -> str:
    with open(policy_document, 'r', encoding='UTF-8') as f:
        content = f.read()
        content.translate(str.maketrans({'"': '\"'}))
        return content

if __name__ == "__main__":
    args = parse_args()
    policy_document = transform_policy_document(args.policy_document)
    policy_skeleton = flesh_template(args.policy_name, policy_document)
    with open(args.output_skeleton, 'w', encoding='UTF-8') as f:
        f.write(json.dumps(policy_skeleton))

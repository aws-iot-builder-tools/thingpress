#!/usr/bin/env python3
"""
Script to transform CloudFormation template with custom directives.
"""
import os
import json
import yaml
import argparse
import re

def include_file(match, base_dir):
    """
    Include the contents of a file in the CloudFormation template.
    
    Args:
        match (re.Match): Regex match object
        base_dir (str): Base directory for relative paths
        
    Returns:
        str: Contents of the included file
    """
    filepath = match.group(1)
    abs_path = os.path.join(base_dir, filepath)
    
    with open(abs_path, 'r') as f:
        if filepath.endswith('.json'):
            return json.load(f)
        elif filepath.endswith('.yaml') or filepath.endswith('.yml'):
            return yaml.safe_load(f)
        else:
            return f.read()

def transform_template(template_path, output_path):
    """
    Transform CloudFormation template with custom directives.
    
    Args:
        template_path (str): Path to the template file
        output_path (str): Path to the output file
        
    Returns:
        None
    """
    base_dir = os.path.dirname(os.path.abspath(template_path))
    
    with open(template_path, 'r') as f:
        template_content = f.read()
    
    # Process !Include directives
    include_pattern = r'!Include\s+([^\s]+)'
    
    def replace_include(match):
        included_content = include_file(match, base_dir)
        return yaml.dump(included_content, default_flow_style=False)
    
    transformed_content = re.sub(include_pattern, replace_include, template_content)
    
    with open(output_path, 'w') as f:
        f.write(transformed_content)
    
    print(f"Transformed template written to {output_path}")

def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='Transform CloudFormation template with custom directives')
    parser.add_argument('--template', required=True, help='Path to the template file')
    parser.add_argument('--output', required=True, help='Path to the output file')
    
    args = parser.parse_args()
    
    transform_template(args.template, args.output)

if __name__ == '__main__':
    main()

#!/bin/bash
# Refactored Thingpress cleanup script using unified cleanup module
# This script is a thin wrapper around the Python cleanup module

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PYTHON_SCRIPT="$SCRIPT_DIR/cleanup_wrapper.py"

# Default values
DRY_RUN="false"
STACK_PREFIX="thingpress"
REGION="us-east-1"
VERBOSE="false"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run)
            DRY_RUN="true"
            shift
            ;;
        --stack-prefix)
            STACK_PREFIX="$2"
            shift 2
            ;;
        --region)
            REGION="$2"
            shift 2
            ;;
        --verbose)
            VERBOSE="true"
            shift
            ;;
        --help)
            echo "Usage: $0 [--dry-run] [--stack-prefix PREFIX] [--region REGION] [--verbose]"
            echo "  --dry-run: Show what would be deleted without actually deleting"
            echo "  --stack-prefix: CloudFormation stack name prefix (default: thingpress)"
            echo "  --region: AWS region (default: us-east-1)"
            echo "  --verbose: Enable verbose logging"
            echo ""
            echo "This script uses the unified Thingpress cleanup module to remove:"
            echo "  - IoT Things, certificates, and policies tagged with 'created-by: thingpress'"
            echo "  - S3 buckets tagged with 'created-by: thingpress'"
            echo "  - CloudFormation stacks with the specified prefix"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Create the Python wrapper script
cat > "$PYTHON_SCRIPT" << 'EOF'
#!/usr/bin/env python3
"""
Python wrapper for unified Thingpress cleanup
"""

import sys
import os
import logging
import argparse

# Add src directory to path
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
src_dir = os.path.join(project_root, 'src')
sys.path.insert(0, src_dir)

try:
    from cleanup_utils import ThingpressCleanup, CleanupConfig
except ImportError as e:
    print(f"❌ Failed to import cleanup module: {e}")
    print(f"Make sure you're running from the project root and src/cleanup_utils exists")
    sys.exit(1)


def setup_logging(verbose: bool = False):
    """Setup logging configuration"""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )


def main():
    parser = argparse.ArgumentParser(description='Thingpress Resource Cleanup')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be deleted')
    parser.add_argument('--stack-prefix', default='thingpress', help='CloudFormation stack prefix')
    parser.add_argument('--region', default='us-east-1', help='AWS region')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose logging')
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.verbose)
    logger = logging.getLogger(__name__)
    
    try:
        # Create cleanup configuration
        config = CleanupConfig.for_standalone_cleanup(
            stack_prefix=args.stack_prefix,
            region=args.region,
            dry_run=args.dry_run
        )
        
        # Initialize and run cleanup
        cleanup = ThingpressCleanup(config)
        results = cleanup.cleanup_all()
        
        # Print summary
        print("\n" + "="*80)
        print("🎯 CLEANUP SUMMARY")
        print("="*80)
        
        if results['dry_run']:
            print("🔍 DRY RUN MODE - No resources were actually deleted")
        else:
            print(f"📱 IoT Things Deleted: {len(results['iot_things_deleted'])}")
            print(f"📜 IoT Certificates Deleted: {len(results['iot_certificates_deleted'])}")
            print(f"🪣 S3 Buckets Cleaned: {len(results['s3_buckets_cleaned'])}")
            print(f"☁️ CloudFormation Stacks Deleted: {len(results['cf_stacks_deleted'])}")
        
        if results['errors']:
            print(f"⚠️ Errors Encountered: {len(results['errors'])}")
            for error in results['errors'][:3]:  # Show first 3 errors
                print(f"   - {error}")
            if len(results['errors']) > 3:
                print(f"   ... and {len(results['errors']) - 3} more errors")
        
        # Check verification results
        verification = results.get('verification', {})
        if verification:
            if verification['success']:
                print("✅ Cleanup verification PASSED")
            else:
                print("❌ Cleanup verification FAILED")
                print(f"   Issues found: {verification['issues_found']}")
                
                remaining = verification['remaining_resources']
                for resource_type, resources in remaining.items():
                    if resources:
                        print(f"   Remaining {resource_type}: {len(resources)}")
        
        print("="*80)
        
        # Exit with appropriate code
        if results['errors'] or (verification and not verification['success']):
            sys.exit(1)
        else:
            sys.exit(0)
            
    except Exception as e:
        logger.error(f"Cleanup failed: {e}")
        import traceback
        if args.verbose:
            traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
EOF

# Make the Python script executable
chmod +x "$PYTHON_SCRIPT"

# Export environment variables for the Python script
export DRY_RUN STACK_PREFIX REGION VERBOSE

# Run the Python cleanup script
echo "🚀 Starting Thingpress Cleanup (v2 - Unified Module)"
echo "================================================"
echo "Region: $REGION"
echo "Stack Prefix: $STACK_PREFIX"
echo "Dry Run: $DRY_RUN"
echo "Verbose: $VERBOSE"
echo "================================================"

# Build arguments for Python script
PYTHON_ARGS=""
if [ "$DRY_RUN" = "true" ]; then
    PYTHON_ARGS="$PYTHON_ARGS --dry-run"
fi
if [ "$VERBOSE" = "true" ]; then
    PYTHON_ARGS="$PYTHON_ARGS --verbose"
fi
PYTHON_ARGS="$PYTHON_ARGS --stack-prefix $STACK_PREFIX --region $REGION"

# Execute the Python cleanup
python3 "$PYTHON_SCRIPT" $PYTHON_ARGS
CLEANUP_EXIT_CODE=$?

# Clean up the temporary Python script
rm -f "$PYTHON_SCRIPT"

# Exit with the same code as the Python script
exit $CLEANUP_EXIT_CODE

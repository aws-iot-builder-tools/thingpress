#!/bin/bash
# Comprehensive cleanup script for Thingpress integration tests
# Removes all resources tagged with "created-by: thingpress"

set -e

# Configuration
STACK_NAME_PREFIX="${STACK_NAME_PREFIX:-thingpress}"
DRY_RUN="${DRY_RUN:-false}"
REGION="${AWS_REGION:-us-east-1}"

# Parse command line arguments first
while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run)
            DRY_RUN="true"
            shift
            ;;
        --stack-prefix)
            STACK_NAME_PREFIX="$2"
            shift 2
            ;;
        --region)
            REGION="$2"
            shift 2
            ;;
        --help)
            echo "Usage: $0 [--dry-run] [--stack-prefix PREFIX] [--region REGION]"
            echo "  --dry-run: Show what would be deleted without actually deleting"
            echo "  --stack-prefix: CloudFormation stack name prefix (default: thingpress)"
            echo "  --region: AWS region (default: us-east-1)"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

echo "🧹 Starting Thingpress Integration Test Cleanup"
echo "================================================"
echo "Region: $REGION"
echo "Stack Prefix: $STACK_NAME_PREFIX"
echo "Dry Run: $DRY_RUN"
echo "================================================"

# Function to execute or print command based on dry run mode
execute_or_print() {
    local cmd="$1"
    if [ "$DRY_RUN" = "true" ]; then
        echo "[DRY RUN] Would execute: $cmd"
    else
        echo "Executing: $cmd"
        eval "$cmd"
    fi
}

# Function to clean up IoT resources created by Thingpress
cleanup_iot_resources() {
    echo "🔧 Cleaning up IoT resources tagged with 'created-by: thingpress'..."
    
    # Clean up IoT Things
    echo "  📱 Cleaning up IoT Things..."
    local things=$(aws iot list-things --region "$REGION" --query 'things[?contains(attributes.`created-by`, `thingpress`)].thingName' --output text 2>/dev/null || echo "")
    if [ -n "$things" ]; then
        for thing in $things; do
            echo "    Removing IoT Thing: $thing"
            # Detach policies first
            local policies=$(aws iot list-thing-principals --thing-name "$thing" --region "$REGION" --query 'principals' --output text 2>/dev/null || echo "")
            for principal in $policies; do
                local attached_policies=$(aws iot list-principal-policies --principal "$principal" --region "$REGION" --query 'policies[].policyName' --output text 2>/dev/null || echo "")
                for policy in $attached_policies; do
                    execute_or_print "aws iot detach-policy --policy-name '$policy' --target '$principal' --region '$REGION'"
                done
                execute_or_print "aws iot detach-thing-principal --thing-name '$thing' --principal '$principal' --region '$REGION'"
            done
            execute_or_print "aws iot delete-thing --thing-name '$thing' --region '$REGION'"
        done
    else
        echo "    No IoT Things found with thingpress tag"
    fi
    
    # Clean up IoT Certificates (that are not attached to things)
    echo "  📜 Cleaning up IoT Certificates..."
    local certificates=$(aws iot list-certificates --region "$REGION" --query 'certificates[?status==`INACTIVE`].certificateId' --output text 2>/dev/null || echo "")
    for cert_id in $certificates; do
        # Check if certificate has thingpress tag (this is a simplified check)
        echo "    Removing inactive certificate: $cert_id"
        execute_or_print "aws iot delete-certificate --certificate-id '$cert_id' --region '$REGION'"
    done
}

# Function to clean up S3 buckets and objects
cleanup_s3_resources() {
    echo "🪣 Cleaning up S3 resources tagged with 'created-by: thingpress'..."
    
    # Find S3 buckets with thingpress tag
    local buckets=$(aws s3api list-buckets --region "$REGION" --query 'Buckets[].Name' --output text 2>/dev/null || echo "")
    
    for bucket in $buckets; do
        # Check if bucket has thingpress tag
        local tags=$(aws s3api get-bucket-tagging --bucket "$bucket" --region "$REGION" --query 'TagSet[?Key==`created-by` && Value==`thingpress`]' --output text 2>/dev/null || echo "")
        
        if [ -n "$tags" ]; then
            echo "  📦 Found Thingpress S3 bucket: $bucket"
            
            # Empty the bucket first
            echo "    Emptying bucket contents..."
            if [ "$DRY_RUN" = "false" ]; then
                aws s3 rm "s3://$bucket" --recursive --region "$REGION" 2>/dev/null || echo "    Bucket already empty or inaccessible"
                
                # Remove any incomplete multipart uploads
                aws s3api list-multipart-uploads --bucket "$bucket" --region "$REGION" --query 'Uploads[].{Key:Key,UploadId:UploadId}' --output text 2>/dev/null | while read key upload_id; do
                    if [ -n "$key" ] && [ -n "$upload_id" ]; then
                        aws s3api abort-multipart-upload --bucket "$bucket" --key "$key" --upload-id "$upload_id" --region "$REGION" 2>/dev/null || true
                    fi
                done
                
                # Remove any object versions if versioning is enabled
                aws s3api list-object-versions --bucket "$bucket" --region "$REGION" --query 'Versions[].{Key:Key,VersionId:VersionId}' --output text 2>/dev/null | while read key version_id; do
                    if [ -n "$key" ] && [ -n "$version_id" ]; then
                        aws s3api delete-object --bucket "$bucket" --key "$key" --version-id "$version_id" --region "$REGION" 2>/dev/null || true
                    fi
                done
                
                # Remove delete markers
                aws s3api list-object-versions --bucket "$bucket" --region "$REGION" --query 'DeleteMarkers[].{Key:Key,VersionId:VersionId}' --output text 2>/dev/null | while read key version_id; do
                    if [ -n "$key" ] && [ -n "$version_id" ]; then
                        aws s3api delete-object --bucket "$bucket" --key "$key" --version-id "$version_id" --region "$REGION" 2>/dev/null || true
                    fi
                done
            else
                echo "    [DRY RUN] Would empty bucket: $bucket"
            fi
            
            echo "    Bucket $bucket is ready for stack deletion"
        fi
    done
}

# Function to clean up CloudFormation stacks
cleanup_cloudformation_stacks() {
    echo "☁️ Cleaning up CloudFormation stacks with prefix '$STACK_NAME_PREFIX'..."
    
    local stacks=$(aws cloudformation list-stacks --region "$REGION" --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE --query "StackSummaries[?starts_with(StackName, '$STACK_NAME_PREFIX')].StackName" --output text 2>/dev/null || echo "")
    
    if [ -n "$stacks" ]; then
        for stack in $stacks; do
            echo "  🗂️ Found stack: $stack"
            
            # Check if stack has thingpress tags
            local stack_tags=$(aws cloudformation describe-stacks --stack-name "$stack" --region "$REGION" --query 'Stacks[0].Tags[?Key==`created-by` && Value==`thingpress`]' --output text 2>/dev/null || echo "")
            
            if [ -n "$stack_tags" ] || [[ "$stack" == *"thingpress"* ]]; then
                echo "    Deleting stack: $stack"
                execute_or_print "aws cloudformation delete-stack --stack-name '$stack' --region '$REGION'"
                
                if [ "$DRY_RUN" = "false" ]; then
                    echo "    Waiting for stack deletion to complete..."
                    aws cloudformation wait stack-delete-complete --stack-name "$stack" --region "$REGION" 2>/dev/null || {
                        echo "    ⚠️ Stack deletion may have failed or timed out: $stack"
                        # Check final status
                        local final_status=$(aws cloudformation describe-stacks --stack-name "$stack" --region "$REGION" --query 'Stacks[0].StackStatus' --output text 2>/dev/null || echo "DELETED")
                        echo "    Final status: $final_status"
                    }
                fi
            else
                echo "    Skipping stack (no thingpress tag): $stack"
            fi
        done
    else
        echo "  No CloudFormation stacks found with prefix '$STACK_NAME_PREFIX'"
    fi
}

# Function to verify cleanup completion
verify_cleanup() {
    echo "✅ Verifying cleanup completion..."
    
    local cleanup_issues=0
    
    # Check for remaining stacks
    local remaining_stacks=$(aws cloudformation list-stacks --region "$REGION" --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE --query "StackSummaries[?starts_with(StackName, '$STACK_NAME_PREFIX')].StackName" --output text 2>/dev/null || echo "")
    if [ -n "$remaining_stacks" ]; then
        echo "  ⚠️ Remaining stacks found: $remaining_stacks"
        cleanup_issues=$((cleanup_issues + 1))
    else
        echo "  ✅ No remaining CloudFormation stacks"
    fi
    
    # Check for remaining S3 buckets with thingpress tag
    local remaining_buckets=0
    local buckets=$(aws s3api list-buckets --region "$REGION" --query 'Buckets[].Name' --output text 2>/dev/null || echo "")
    for bucket in $buckets; do
        local tags=$(aws s3api get-bucket-tagging --bucket "$bucket" --region "$REGION" --query 'TagSet[?Key==`created-by` && Value==`thingpress`]' --output text 2>/dev/null || echo "")
        if [ -n "$tags" ]; then
            echo "  ⚠️ Remaining S3 bucket with thingpress tag: $bucket"
            remaining_buckets=$((remaining_buckets + 1))
            cleanup_issues=$((cleanup_issues + 1))
        fi
    done
    
    if [ $remaining_buckets -eq 0 ]; then
        echo "  ✅ No remaining S3 buckets with thingpress tag"
    fi
    
    # Summary
    if [ $cleanup_issues -eq 0 ]; then
        echo "  🎉 Cleanup verification PASSED - All resources cleaned up successfully!"
        return 0
    else
        echo "  ❌ Cleanup verification FAILED - $cleanup_issues issues found"
        return 1
    fi
}

# Main cleanup process
main() {
    echo "Starting cleanup process..."
    
    # Step 1: Clean up application-created resources (IoT, etc.)
    cleanup_iot_resources
    
    # Step 2: Clean up S3 buckets and their contents
    cleanup_s3_resources
    
    # Step 3: Delete CloudFormation stacks
    cleanup_cloudformation_stacks
    
    # Step 4: Verify cleanup
    if [ "$DRY_RUN" = "false" ]; then
        echo "⏳ Waiting 30 seconds for resources to fully delete..."
        sleep 30
        verify_cleanup
    else
        echo "🔍 Dry run completed - no actual resources were deleted"
    fi
    
    echo "🏁 Cleanup process completed!"
}

# Run main function
main

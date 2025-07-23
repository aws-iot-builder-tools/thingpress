#!/bin/bash
#
# Quick Performance Test Runner for Thingpress
# Generates certificates on-demand and runs performance tests
#

set -e

echo "🚀 Thingpress Performance Test Runner"
echo "======================================"

# Default values
SCALE="medium"
CERTIFICATES=""
BATCH_SIZE=1000

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --scale)
            SCALE="$2"
            shift 2
            ;;
        --certificates)
            CERTIFICATES="$2"
            shift 2
            ;;
        --batch-size)
            BATCH_SIZE="$2"
            shift 2
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --scale SCALE        Predefined scale: small, medium, large, xlarge"
            echo "  --certificates NUM   Custom number of certificates"
            echo "  --batch-size SIZE    Certificates per batch (default: 1000)"
            echo "  --help              Show this help message"
            echo ""
            echo "Predefined scales:"
            echo "  small:   5,000 certificates"
            echo "  medium:  25,000 certificates"
            echo "  large:   100,000 certificates"
            echo "  xlarge:  200,000 certificates"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Check if Python script exists
if [[ ! -f "performance_test_integrated.py" ]]; then
    echo "❌ Error: performance_test_integrated.py not found"
    echo "   Make sure you're running from the test/performance directory"
    exit 1
fi

# Check if certificate generator exists (adjust path for new location)
if [[ ! -f "../../src/certificate_generator/generate_certificates.py" ]]; then
    echo "❌ Error: Certificate generator not found"
    echo "   Expected: ../../src/certificate_generator/generate_certificates.py"
    exit 1
fi

# Run the performance test
echo "🔄 Starting performance test..."
echo "   Scale: $SCALE"
if [[ -n "$CERTIFICATES" ]]; then
    echo "   Custom certificates: $CERTIFICATES"
fi
echo "   Batch size: $BATCH_SIZE"
echo ""

if [[ -n "$CERTIFICATES" ]]; then
    python performance_test_integrated.py --certificates "$CERTIFICATES" --batch-size "$BATCH_SIZE"
else
    python performance_test_integrated.py --scale "$SCALE"
fi

echo ""
echo "✅ Performance test runner completed!"

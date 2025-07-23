# Thingpress Performance Testing

This directory contains performance testing tools for Thingpress that generate certificates on-demand and validate system performance at scale.

## 📁 Location

Performance testing is located in `test/performance/` to align with the project's testing structure:
- `test/unit/` - Unit tests
- `test/integration/` - Integration tests  
- `test/performance/` - Performance tests

## 🎯 Overview

The performance testing system:
- **Generates certificates on-demand** (no large files in git)
- **Tests multiple scales** from 5K to 200K certificates
- **Uses optimal batch sizes** (1,000 certificates per batch)
- **Validates end-to-end performance** including upload and processing
- **Cleans up automatically** (no temporary files left behind)

## 🚀 Quick Start

### Navigate to Performance Test Directory
```bash
cd test/performance
```

### Run Predefined Scale Tests

```bash
# Small scale test (5,000 certificates)
./run_performance_test.sh --scale small

# Medium scale test (25,000 certificates) 
./run_performance_test.sh --scale medium

# Large scale test (100,000 certificates)
./run_performance_test.sh --scale large

# Extra large scale test (200,000 certificates)
./run_performance_test.sh --scale xlarge
```

### Run Custom Tests

```bash
# Custom certificate count
./run_performance_test.sh --certificates 50000

# Custom batch size
./run_performance_test.sh --certificates 10000 --batch-size 500

# Python interface
python performance_test_integrated.py --certificates 25000 --batch-size 1000
```

## 📊 Performance Metrics

Based on comprehensive testing, Thingpress achieves:

### Optimal Configuration
- **Batch size**: 1,000 certificates per file
- **Processing time**: ~2.4 minutes per batch
- **Memory usage**: ~125MB per Lambda execution
- **Timeout margin**: 50% safety margin (147s vs 300s limit)

### Performance Results
- **Upload throughput**: 250-400 certificates/second
- **Processing throughput**: ~7 certificates/second per batch
- **Parallel processing**: 10+ concurrent Lambda executions
- **Effective throughput**: ~70+ certificates/second (with parallelism)
- **Scale capability**: 200,000+ certificates validated

### Production Projections
- **200,000 certificates**: ~1 hour processing time with parallelism
- **Expected throughput**: ~55,000 certificates/hour
- **Reliability**: 100% success rate in testing

## 🔧 Technical Details

### Certificate Generation
- Uses `../../src/certificate_generator/generate_certificates.py`
- Generates EC P-256 certificates with full CA chain
- Creates optimally-sized batches automatically
- Generation rate: ~14,000 certificates/second

### Test Process
1. **Setup**: Creates temporary directory
2. **Generate**: Creates certificates on-demand
3. **Upload**: Uploads batches to S3 with timing
4. **Monitor**: Provides CloudWatch monitoring guidance
5. **Cleanup**: Removes all temporary files

### File Structure
```
test/performance/
├── performance_test_integrated.py    # Main integrated test script
├── run_performance_test.sh          # Bash wrapper for easy execution
└── PERFORMANCE_TESTING.md           # This documentation
```

## 📈 Monitoring

### CloudWatch Logs
Monitor processing progress in:
```
/aws/lambda/sam-app-ThingpressGeneratedProviderFunction-*
```

### Key Log Messages
- `"Processing certificate file"` - Batch processing started
- `"Total certificates processed"` - Batch completed successfully
- Look for `count: 1000` to confirm full batch processing

### SQS Queue Monitoring
```bash
aws sqs get-queue-attributes \
  --queue-url "https://sqs.us-east-1.amazonaws.com/517295686160/Thingpress-Generated-Provider-Queue-sam-app" \
  --attribute-names ApproximateNumberOfMessages,ApproximateNumberOfMessagesNotVisible
```

## 🎯 Scale Test Definitions

| Scale  | Certificates | Batches | Est. Time | Use Case |
|--------|-------------|---------|-----------|----------|
| small  | 5,000       | 5       | ~2 min    | Quick validation |
| medium | 25,000      | 25      | ~10 min   | Integration testing |
| large  | 100,000     | 100     | ~40 min   | Load testing |
| xlarge | 200,000     | 200     | ~80 min   | Production scale |

## 🔍 Troubleshooting

### Common Issues

**Certificate generation fails:**
- Ensure `../../src/certificate_generator/generate_certificates.py` exists
- Check Python dependencies are installed
- Make sure you're running from `test/performance/` directory

**Upload failures:**
- Verify AWS credentials are configured
- Check S3 bucket permissions
- Ensure bucket name is correct in script

**Processing timeouts:**
- Monitor Lambda timeout settings (should be 300s)
- Check for batch sizes > 1000 certificates
- Verify Lambda memory allocation (256MB minimum)

### Performance Optimization

**For faster uploads:**
- Reduce batch size to 500-750 certificates
- Increase upload parallelism (modify script)

**For faster processing:**
- Increase Lambda memory allocation
- Optimize Lambda timeout settings
- Consider SQS batch size adjustments

## 🎉 Success Criteria

A successful performance test should show:
- ✅ 100% upload success rate
- ✅ All batches process within 300s timeout
- ✅ Consistent ~1000 certificates per batch completion
- ✅ No Lambda errors or timeouts
- ✅ Expected throughput rates achieved

## 📝 Contributing

When adding new performance tests:
1. **Never commit generated certificate files**
2. **Use temporary directories with cleanup**
3. **Follow the on-demand generation pattern**
4. **Include proper error handling and cleanup**
5. **Document expected performance metrics**

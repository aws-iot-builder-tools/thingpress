# SQS Optimization Implementation Plan

## 🎯 Overview

This document outlines the implementation plan for two key SQS optimizations in Thingpress:

1. **SQS Batch Send Mechanism**: Reduce API calls by batching certificate messages
2. **Automatic SQS Throttling**: Replace manual throttling with SQS-native mechanisms

## 📊 Current State Analysis

### Message Flow
```
S3 Upload → Product Verifier → Provider Queue → Provider Function → Bulk Importer Queue → Bulk Importer
```

### Current Bottlenecks
- **1 certificate = 1 SQS message = 1 API call**
- **Manual throttling** in performance tests
- **High API call volume** for large certificate batches

### Current Configuration
- **SQS BatchSize: 10** (Lambda trigger)
- **VisibilityTimeout: 900s** (15 minutes)
- **Individual send_message()** calls

## 🚀 Optimization 1: SQS Batch Send Mechanism

### Benefits
- **10x reduction** in SQS API calls (1 call for 10 certificates vs 10 calls)
- **Improved throughput**: ~55K certs/hour → ~200K+ certs/hour potential
- **Cost reduction**: Fewer SQS API calls
- **Better error handling**: Batch retry mechanisms

### Implementation Strategy

#### Phase 1: Enhanced aws_utils.py
```python
def send_sqs_message_batch(messages, queue_url, session=default_session):
    """Send multiple messages in a single SQS batch operation"""
    sqs_client = session.client('sqs')
    
    # SQS batch limit is 10 messages
    batch_size = 10
    results = []
    
    for i in range(0, len(messages), batch_size):
        batch = messages[i:i + batch_size]
        entries = []
        
        for idx, message in enumerate(batch):
            entries.append({
                'Id': str(i + idx),
                'MessageBody': dumps(message)
            })
        
        try:
            response = sqs_client.send_message_batch(
                QueueUrl=queue_url,
                Entries=entries
            )
            results.append(response)
            
            # Handle partial failures
            if 'Failed' in response and response['Failed']:
                logger.warning(f"Batch send partial failure: {response['Failed']}")
                
        except ClientError as error:
            boto_exception(error, f"Batch send failed for queue {queue_url}")
            raise error
    
    return results
```

#### Phase 2: Provider Function Updates
```python
# In provider functions - batch certificate processing
def process_certificates_batch(certificates, config, queue_url, session):
    """Process certificates in batches for optimal SQS throughput"""
    batch_messages = []
    batch_size = 10  # SQS batch limit
    
    for certificate in certificates:
        cert_config = config.copy()
        cert_config['certificate'] = certificate
        cert_config['thing'] = get_cn(base64.b64decode(certificate))
        
        batch_messages.append(cert_config)
        
        # Send batch when full
        if len(batch_messages) >= batch_size:
            send_sqs_message_batch(batch_messages, queue_url, session)
            batch_messages = []
    
    # Send remaining messages
    if batch_messages:
        send_sqs_message_batch(batch_messages, queue_url, session)
```

#### Phase 3: Error Handling & Monitoring
```python
def send_sqs_message_batch_with_retry(messages, queue_url, session, max_retries=3):
    """Enhanced batch send with retry logic"""
    for attempt in range(max_retries):
        try:
            response = send_sqs_message_batch(messages, queue_url, session)
            
            # Check for partial failures and retry failed messages
            failed_messages = []
            for batch_response in response:
                if 'Failed' in batch_response:
                    for failure in batch_response['Failed']:
                        failed_messages.append(messages[int(failure['Id'])])
            
            if failed_messages and attempt < max_retries - 1:
                messages = failed_messages
                continue
            
            return response
            
        except ClientError as error:
            if attempt == max_retries - 1:
                raise error
            time.sleep(2 ** attempt)  # Exponential backoff
```

### Performance Impact Estimation
- **Current**: 1,000 certificates = 1,000 SQS API calls
- **Optimized**: 1,000 certificates = 100 SQS API calls (10x improvement)
- **Throughput increase**: 55K certs/hour → 200K+ certs/hour potential

## 🎛️ Optimization 2: Automatic SQS Throttling

### Current Manual Throttling Issues
```python
# Performance test manual delays
time.sleep(30)  # Hard-coded, inflexible
```

### Proposed Solutions

#### Option A: SQS Delay Queues (Recommended)
```yaml
# In template.yaml
ThingpressProviderQueue:
  Type: AWS::SQS::Queue
  Properties:
    DelaySeconds: 30  # Built-in 30-second delay
    VisibilityTimeout: 900
```

**Benefits:**
- **Native SQS feature** - no custom code
- **Automatic throttling** without Lambda changes
- **Configurable per queue**

#### Option B: Lambda Reserved Concurrency
```yaml
# In template.yaml
ThingpressProviderFunction:
  Type: AWS::Serverless::Function
  Properties:
    ReservedConcurrencyUnits: 2  # Limit concurrent executions
```

**Benefits:**
- **Automatic concurrency control**
- **Prevents overwhelming downstream systems**
- **Built-in AWS feature**

#### Option C: Message Attributes with Conditional Processing
```python
def send_with_throttling(message, queue_url, delay_seconds=30):
    """Send message with processing delay"""
    process_after = int(time.time()) + delay_seconds
    
    message_attributes = {
        'ProcessAfter': {
            'StringValue': str(process_after),
            'DataType': 'Number'
        }
    }
    
    sqs_client.send_message(
        QueueUrl=queue_url,
        MessageBody=dumps(message),
        MessageAttributes=message_attributes
    )

def should_process_message(message):
    """Check if message should be processed based on timestamp"""
    if 'MessageAttributes' in message and 'ProcessAfter' in message['MessageAttributes']:
        process_after = int(message['MessageAttributes']['ProcessAfter']['StringValue'])
        return time.time() >= process_after
    return True
```

### Recommended Approach: Hybrid Solution

#### 1. SQS Delay Queues for Batch Throttling
```yaml
# Different delay queues for different throttling needs
ThingpressProviderQueueImmediate:
  Type: AWS::SQS::Queue
  Properties:
    DelaySeconds: 0

ThingpressProviderQueueThrottled:
  Type: AWS::SQS::Queue  
  Properties:
    DelaySeconds: 30  # 30-second throttling
```

#### 2. Lambda Reserved Concurrency for System Protection
```yaml
ReservedConcurrencyUnits: 5  # Allow max 5 concurrent executions
```

#### 3. Dynamic Throttling Based on Queue Depth
```python
def get_optimal_delay(queue_url, session):
    """Calculate optimal delay based on queue depth"""
    sqs_client = session.client('sqs')
    
    attrs = sqs_client.get_queue_attributes(
        QueueUrl=queue_url,
        AttributeNames=['ApproximateNumberOfMessages']
    )
    
    queue_depth = int(attrs['Attributes']['ApproximateNumberOfMessages'])
    
    # Dynamic delay based on queue depth
    if queue_depth > 1000:
        return 60  # 1 minute delay for high load
    elif queue_depth > 500:
        return 30  # 30 second delay for medium load
    else:
        return 0   # No delay for low load
```

## 📈 Implementation Phases

### Phase 1: SQS Batch Implementation (Week 1)
1. **Update aws_utils.py** with batch send functions
2. **Modify provider functions** to use batch sending
3. **Add comprehensive error handling**
4. **Update unit tests**

### Phase 2: Throttling Implementation (Week 2)
1. **Add SQS delay queue configuration**
2. **Implement Lambda reserved concurrency**
3. **Add dynamic throttling logic**
4. **Performance testing and tuning**

### Phase 3: Integration & Testing (Week 3)
1. **End-to-end testing** with both optimizations
2. **Performance benchmarking**
3. **Monitoring and alerting setup**
4. **Documentation updates**

## 🎯 Expected Outcomes

### Performance Improvements
- **API call reduction**: 90% fewer SQS API calls
- **Throughput increase**: 3-4x improvement in certificate processing
- **Cost reduction**: Significant SQS API cost savings
- **Reliability**: Better error handling and retry mechanisms

### Operational Benefits
- **Automatic throttling**: No manual intervention needed
- **Scalable**: Handles varying load automatically
- **Monitoring**: Better visibility into processing patterns
- **Maintainable**: Less complex performance test code

## 🔍 Monitoring & Metrics

### Key Metrics to Track
- **SQS API call volume** (should decrease significantly)
- **Message processing latency**
- **Batch success/failure rates**
- **Queue depth over time**
- **Lambda concurrency utilization**

### CloudWatch Alarms
- **High queue depth** (> 1000 messages)
- **Batch failure rate** (> 5%)
- **Processing latency** (> 5 minutes)
- **DLQ message count** (> 0)

## 🚨 Risks & Mitigation

### Potential Risks
1. **Batch processing complexity**
2. **Partial failure handling**
3. **Message ordering concerns**
4. **Increased memory usage**

### Mitigation Strategies
1. **Comprehensive error handling** with retry logic
2. **Monitoring and alerting** for batch failures
3. **Gradual rollout** with feature flags
4. **Rollback plan** to individual message sending

## 📋 Success Criteria

### Technical Success
- ✅ **90% reduction** in SQS API calls
- ✅ **3x throughput improvement** in performance tests
- ✅ **Zero message loss** during batch processing
- ✅ **Automatic throttling** working without manual intervention

### Operational Success
- ✅ **Reduced operational overhead** for large deployments
- ✅ **Cost savings** from fewer API calls
- ✅ **Improved reliability** with better error handling
- ✅ **Scalable solution** for enterprise deployments

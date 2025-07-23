# S3 Bucket Notification Configuration Alternatives

## Option 2: Native CloudFormation Approach (Recommended for Simplicity)

Replace the custom resource with a simpler approach using native CloudFormation resources:

```yaml
# Remove the custom resource entirely and use this approach instead:

# Step 1: Create a separate S3 bucket specifically for Microchip notifications
ThingpressMicrochipNotificationBucket:
  Type: AWS::S3::Bucket
  DependsOn: 
    - ThingpressMicrochipVerifierCertificates
    - ThingpressProductProviderInvokeFromMicrochipPerm
  Properties:
    BucketName: !Sub thingpress-microchip-notifications-${AWS::StackName}
    BucketEncryption:
      ServerSideEncryptionConfiguration:
        - ServerSideEncryptionByDefault:
            SSEAlgorithm: aws:kms
            KMSMasterKeyID: alias/aws/s3
    VersioningConfiguration:
      Status: Enabled
    PublicAccessBlockConfiguration:
      BlockPublicAcls: true
      BlockPublicPolicy: true
      IgnorePublicAcls: true
      RestrictPublicBuckets: true
    NotificationConfiguration:
      LambdaConfigurations:
        - Event: s3:ObjectCreated:*
          Filter:
            S3Key:
              Rules:
                - Name: suffix
                  Value: .json
          Function: !GetAtt ThingpressProductProviderFunction.Arn

# Step 2: Use a Lambda function to copy objects from main bucket to notification bucket
ThingpressMicrochipObjectCopier:
  Type: AWS::Serverless::Function
  Properties:
    CodeUri: src/object_copier/
    Handler: app.lambda_handler
    Runtime: python3.13
    Timeout: 60
    Policies:
      - S3ReadPolicy:
          BucketName: !Ref ThingpressMicrochipManifestBucket
      - S3CrudPolicy:
          BucketName: !Ref ThingpressMicrochipNotificationBucket
    Events:
      S3Event:
        Type: S3
        Properties:
          Bucket: !Ref ThingpressMicrochipManifestBucket
          Events: s3:ObjectCreated:*
          Filter:
            S3Key:
              Rules:
                - Name: Suffix
                  Value: .json
```

## Option 3: Conditional Notification Configuration

Use CloudFormation conditions to enable notifications only after certificates are deployed:

```yaml
Conditions:
  EnableMicrochipNotifications: !Not [!Equals [!Ref "AWS::NoValue", !Ref ThingpressMicrochipVerifierCertificates]]

ThingpressMicrochipManifestBucket:
  Type: AWS::S3::Bucket
  Properties:
    BucketName: !Sub thingpress-microchip-${AWS::StackName}
    # ... other properties
    NotificationConfiguration: !If
      - EnableMicrochipNotifications
      - LambdaConfigurations:
          - Event: s3:ObjectCreated:*
            Filter:
              S3Key:
                Rules:
                  - Name: suffix
                    Value: .json
            Function: !GetAtt ThingpressProductProviderFunction.Arn
      - !Ref "AWS::NoValue"
```

## Option 4: Use AWS::S3::Bucket with DependsOn

Simplest approach - just use proper dependencies:

```yaml
ThingpressMicrochipManifestBucket:
  Type: AWS::S3::Bucket
  DependsOn: 
    - ThingpressMicrochipVerifierCertificates
    - ThingpressProductProviderInvokeFromMicrochipPerm
  Properties:
    BucketName: !Sub thingpress-microchip-${AWS::StackName}
    BucketEncryption:
      ServerSideEncryptionConfiguration:
        - ServerSideEncryptionByDefault:
            SSEAlgorithm: aws:kms
            KMSMasterKeyID: alias/aws/s3
    VersioningConfiguration:
      Status: Enabled
    PublicAccessBlockConfiguration:
      BlockPublicAcls: true
      BlockPublicPolicy: true
      IgnorePublicAcls: true
      RestrictPublicBuckets: true
    NotificationConfiguration:
      LambdaConfigurations:
        - Event: s3:ObjectCreated:*
          Filter:
            S3Key:
              Rules:
                - Name: suffix
                  Value: .json
          Function: !GetAtt ThingpressProductProviderFunction.Arn
```

## Option 5: EventBridge Integration

Use EventBridge instead of direct S3 notifications:

```yaml
# Enable EventBridge for the S3 bucket
ThingpressMicrochipManifestBucket:
  Type: AWS::S3::Bucket
  Properties:
    # ... other properties
    NotificationConfiguration:
      EventBridgeConfiguration:
        EventBridgeEnabled: true

# EventBridge rule to trigger Lambda
ThingpressMicrochipEventRule:
  Type: AWS::Events::Rule
  DependsOn: ThingpressMicrochipVerifierCertificates
  Properties:
    EventPattern:
      source: ["aws.s3"]
      detail-type: ["Object Created"]
      detail:
        bucket:
          name: [!Ref ThingpressMicrochipManifestBucket]
        object:
          key:
            - suffix: ".json"
    Targets:
      - Arn: !GetAtt ThingpressProductProviderFunction.Arn
        Id: MicrochipProcessorTarget
```

## Recommendation

**Option 1** (Fix Custom Resource) is recommended if you want to maintain the two-phase deployment pattern with maximum control.

**Option 4** (Simple DependsOn) is recommended for simplicity and is likely sufficient for most use cases.

**Option 5** (EventBridge) is recommended for enterprise environments that prefer event-driven architectures.

## ESP32-S3 Provider Invocation
1. Obtain the Manifest file and verification certificate from Espressif Systems.
2. Login to the AWS Console.
3. Ensure you are in the target region where your application operates.
4. Navigate to Amazon S3 via the Services menu.
5. Identify the bucket for ESP32-S3. It will be your deployment Stack Name suffixed with "-esp32s3".
6. Upload (or drag and drop) the certificate manifest csv file to the S3.
   bucket.  On this event, the Thingpress tool begins processing the manifest.
7. The certificates and objects will be created and configured in AWS IoT Core.


1. Obtain the Manifest file and verification certificate from Infineon
2. Login to the AWS Console.
3. Ensure you are in the target region where your application operates.
4. Navigate to Amazon S3 via the Services menu.
5. Identify the bucket for Infineon. It will be your deployment Stack Name suffixed with "-infineon".
6. Upload (or drag and drop) the verification certificate.  The
   verification certificate should not have a .json extension.
7. Upload (or drag and drop) the certificate manifest xml file to the S3
   bucket.  On this event, the Thingpress tool begins processing the manifest
8. The certificates and objects will be created and configured in AWS IoT Core.

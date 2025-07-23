
*Note: if any of the terms are unfamiliar, see the Background section*

1. Obtain and download the Manifest file and verification certificate from MicrochipDirect
2. Login to the AWS Console.
3. Ensure you are in the target region where your application operates.
4. Get a current summary of your IoT things and certificates as follows: ```script/get-iot-summary.sh <aws region> ```
5. Navigate to Amazon S3 via the Services menu.
6. Identify the bucket for Microchip. It will be your deployment Stack Name suffixed with "-microchip".
7. Upload (or drag and drop) the verification certificate.  The
   verification certificate should not have a .json extension.
8. Upload (or drag and drop) the certificate manifest to the S3
   bucket.  On this event, the Thingpress tool begins processing the manifest
9. The certificates and objects will be created and configured in AWS IoT Core.
10. Verify that the operation has been succesful (correct number of certificates added, etc.) by getting the updated summary as follows: ```script/get-iot-summary.sh <aws region> ```


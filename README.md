# ThingPress: AWS IoT Certificate Multi-Account Registration Bulk Import

AWS IoT Core supports the capability to import AWS IoT certificates that don't have a registered Certificate Authority. Customers purchase pre-provisioned hardware security components such as secure elements, enclaves, or TPMs that directly ship to contract manufacturing sites.

In parallel, customers receive a list from hardware security suppliers containing copies of the certificates that were provisioned to the hardware security components. This list can consist of up to millions of certificates, each representing the physical component. Importing so many certificates manually is time-consuming and costly. This project simplifies the certificate import and thing provisioning process in AWS using automation.


# Overview

Thingpress provides mechanisms to pipeline mass certificate
processing and subsequent AWS IoT Core configuration.  It is designed
for use at-scale, meaning that it is useful for customers importing
from tens to millions of devices using the Multi-Account Registration
(MAR) mechanism that is provided by AWS IoT Core.  Depending on your
application's maturity, the breadth of your product portfolio, and
your IoT application operations, your IoT device configuration options
may be designed differently.  It is the intent that this tool can
cover the majority of mass import cases.

In IoT Core, an x509 certificate must be registered to the IoT Core
Registry for device authentication. An IoT Core Policy must be
attached to the x509 certificate for device authorization. An IoT Core
Thing object should be attached to the x509 certificate to provide
configuration context.  Applying a Thing Type to a Thing object
standardizes how your application identifies and utilizes Thing
objects.  Aligning a Thing object with a Thing Group further provides
bulk processing capabilities with AWS IoT Device Management, such as 
Over-The-Air (OTA) job management mechanisms. Read the AWS IoT Core
documentation to learn more about these objects and mechanisms.

# Background

The Thingpress importer has three functional components that allow
customization for both the type of hardware security in use and your
product.

- **Supplier Provider**: understands the supplier manifest file
  format. This is the engine that extracts individual certificates and
  stages them for the bulk importer. A different provider may be
  needed for every hardware security component.
- **Product Provider**: allows customization for a specific product
  line.  Customization would be required to define properties such as
  individual device Thing Type, Thing Group, and Policy.
- **Bulk importer**: the bulk importer is common for all product
  providers and supplier providers.  The bulk importer can be called
  directly if the certificate is properly formatted and relevant
  metadata has been passed to it.

The import process can have multiple ingest points and routing:

- **Amazon S3**. The S3 ingest point is required for processes that
  require supplier payload decomposition, such as the Microchip
  manifest.
- **Amazon API Gateway**. (Future implementation)
- **AWS IoT**. (Future implementation) You can use a program that uses
TLS 1.2 authentication and is authorized to pass the certificate to
the importer.  The certificate must be base64 encoded (the default)
and must be unique.

The basic execution is:

1. The supplier manifest provider separates the certificates from
   other supplier specific metadata and pushes individual 
   certificates to the product provider Amazon SQS queue.
2. The product provider listens to this SQS queue.  For each certificate sent to this queu, product line specific metadata is applied to a new message, the certificate is appended, 
and the result is sent to the bulk import SQS queue.
3. The bulk import facility listens to messages being added to the
   bulk import SQS queue and invokes the API calls to import the
   certificate, create any necessary objects (such as Thing), and
   attach any necessary objects (like Thing Groups, Types, and
   Policies).


# Prerequisites

- Amazon Web Services account. If you don't have an account, refer to https://docs.aws.amazon.com/iot/latest/developerguide/setting-up.html.  The relevant sections are **Sign up for an AWS account** and **Create a user and grant permissions**.  
- Basic experience with Amazon CloudFormation 
- Linux workstation or Amazon Linux EC2 instance with:
  - Docker
  - Amazon Web Services Command Line Interface (CLI)
  - Amazon Web Services Serverless Application Model (SAM) CLI
  - Amazon Web Services IAM credentials with appropriate Role
    permissions and programmatic access for: 
        IAM, SQS, S3, Lambda, IoT, CloudFormation, CloudWatch

# Installation

## Step 1: Define required and optional components

Before starting, you must identify the AWS IoT objects you will use at
scale.

- Required: AWS IoT Policy. This policy must be created in AWS IoT Core.
- Optional but highly recommended: AWS IoT Thing Type
- Optional but highly recommended: AWS IoT Thing Group

NOTE: The above items must be defined in the target region prior to running Step
2.

## Step 2: Building and installing the tool

These steps assume you are building and installing the tool on a
GNU/Linux operating system such as a local workstation or EC2 instance
with the appropriate policy and/or IAM programmatic credential.

1. Clone the thingpress repository.

   ```bash
   git clone https://github.com/awslabs/thingpress thingpress
   ```
   
2. Enter the script directory.
   
   ```bash
   cd thingpress/script
   ```
   
3. Invoke the Lambda function build script.  It has been known that
   VPN interrupts this process since it can interfere with Docker
   operation.
   
   ```bash
   ./build.sh
   ```
   
4. Create a private S3 bucket that will be used for deployment

   ```bash
   aws s3api create-bucket --acl private –-bucket <my_unique_s3_bucket>
   ```

5. Invoke the packaging process.  This will copy files to S3 and
   create a ```packaged.yaml`` file that evolves the template.yaml file to use S3
   URLs for deployment.

   ```bash
   ./package.sh <my_unique_s3_bucket>
   ```

6. Invoke the deploy script with a unique stack name and parameters
   for the IoT objects you wish to attach later. Note that during the
   deploy phase these objects are NOT cross-checked for validity.
   
   ```bash
   ./deploy.sh <stackname> <policyname> <thinggroupname> <thingtypename> <s3 bucket name> <aws region> <arn of IAM role> 
   ```

Tool installation is now complete.

# Invocation

You perform invocation based on the Vendor Provider
mechanism. Currently, the following providers are supported:

- Microchip Technology, Inc.
- Infineon

**NOTE** There is a possibility that your account may be throttled for
the ```RegisterCertificateWithoutCA``` API call.  If this occurs,
please contact AWS for a limit increase.  See [AWS IoT Core Endpoints
and
Quotas](https://docs.aws.amazon.com/general/latest/gr/iot-core.html#limits_iot)
page for more information.

## Microchip Provider Invocation

*Note: if any of the terms are unfamiliar, see the Background section*

1. Obtain and download the Manifest file and verification certificate from MicrochipDirect
2. Login to the AWS Console.
3. Ensure you are in the target region where your application operates.
4. Get a current summary of your IoT things and certificates as follows: ```get-iot-summary <aws region> ```
5. Navigate to Amazon S3 via the Services menu.
6. Identify the bucket for Microchip. It will be your deployment Stack Name suffixed with "-microchip".
7. Upload (or drag and drop) the verification certificate.  The
   verification certificate should not have a .json extension.
8. Upload (or drag and drop) the certificate manifest to the S3
   bucket.  On this event, the Thingpress tool begins processing the manifest
9. The certificates and objects will be created and configured in AWS IoT Core.
10. Verify that the operation has been succesful (correct number of certificates added, etc.) by getting the updated summary as follows: ```get-iot-summary <aws region> ```

## Infineon Provider Invocation
**NEED TO CHECK THIS**
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

# Customization / Extension
## Defining the Product Provider

The Product Provider takes an individual certificate, applies product
specific metadata, and stores the file to a target location used by
the bulk importer.

In the product provider, you define the objects that need to be to be
created for the device the certificate represents as well as making
the appropriate associations.

## Defining the Supplier Provider

The Supplier Provider takes an input dropped to an S3 bucket created by
the deployement process, isolates certificates, and puts certificates
to a target Amazon SQS queue.

## Invoking the Product-Supplier-Importer Installation

The installation expects that you are running on a GNU/Linux based
system. Mileage may vary under Mac OSX.  If your workstation is not a
GNU/Linux variant, it may be best to invoke this process from a
t2.micro Amazon Linux instance in the AWS Cloud.

To invoke the installation, you must perform three steps:

1. Package and build Lambda functions
2. Stage Lambda functions and CloudFormation scripts
3. Invoke the CloudFormation script.

# ThingPress: AWS IoT Certificate Multi-Account Registration Bulk Import

In 2019, AWS provided the capability to import AWS IoT certificates to
does not have a registered Certificate Authority.  Customers purchase
pre-provisioned hardware security components such as secure elements,
enclaves, or TPMs that directly ship to contract manufacturing
sites.

In parallel, customers receive a list from hardware security suppliers
containing copies of the certificates that were provisioned to the
hardware security components. Customers can receive a list composing
tens of thousands, hundreds of thousands, or millions of certificates,
each representing the physical component. This project simplifies the
certificate import process.

# Prerequisites

- Amazon Web Services account
- AWS CloudFormation, basic experience
- Linux workstation or Amazon Linux EC2 instance with:
  - Docker
  - Amazon Web Services Command Line Interface (CLI)
  - Amazon Web Services Serverless Application Model (SAM) CLI
  - Amazon Web Services IAM credentials with appropriate Role
    permissions and programmatic access

# Overview

This solution provides mechanisms to pipeline mass certificate
processing and subsequest AWS IoT Core configuration.  It is designed
for use at-scale, meaning that it is useful for customers importing
hundreds to millions of devices using the Multi-Account Registration
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
bulk processing activities with AWS IoT Device Management, for example
Over-The-Air (OTA) job management mechanisms. Read the AWS IoT Core
documentation to learn more about these objects and mechanisms.

# Installation and invocation

## Step 1: Define required and optional components

Before starting, you must identify the AWS IoT objects you will use at
scale.

- Required: AWS IoT Policy
- Optional: AWS IoT Thing Type
- Optional: AWS IoT Thing Group

The objects must be defined in the target region prior to running Step
2.

## Step 2: Building and installing the tool

These steps assume you are building and installing the tool on a
GNU/Linux operating system such as a local workstation or EC2 instance
with the appropriate policy and/or IAM programmatic credential.

1. Clone this repository.

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
   
4. Invoke the packaging process.  This will copy files to S3 and
   create a ```packaged.yaml`` that evolves the template to use S3
   URLs for deployment.

   ```bash
   aws s3api create-bucket <my_unique_s3_bucket>
   ./package.sh <my_unique_s3_bucket>
   ```

5. Invoke the deploy script with a unique stack name and parameters
   for the IoT objects you wish to attach later. Note that during the
   deploy phase these objects are NOT cross-checked for validity.
   
   ```bash
   ./deploy.sh <stackname> <policyname> <typename> <groupname>
   ```

The tool is now installed.

# Invocation

You perform invocation based on the Vendor Provider
mechanism. Currently, the following providers include:

- Microchip Technology, Inc.

**NOTE** There is opportunity that your account may be throttled for
the ```RegisterCertificateWithoutCA``` API call.  When this occurs,
please contact AWS for a limit increase.  See [AWS IoT Core Endpoints
and
Quotas](https://docs.aws.amazon.com/general/latest/gr/iot-core.html#limits_iot)
page for more information.

## Microchip Provider Invocation

*Note: if any of the terms are unfamiliar, see the Processing section*

You begin processing my initiating an event for the Supplier
Provider.  The interface is an Amazon S3 bucket that begins with the
SKU Name.  For example, if you are initiating the process with the
Microchip provider, then you will drop in the Manifest file and
verification certificate that Microchip delivers to you through
Microchip DIRECT.

1. Login to the AWS Console.
2. Ensure you are in the target region where your application operates.
3. Navigate to Amazon S3 via the Services menu.
4. Identify the bucket for the target Supplier Provider.  It will be
   prefix with your deployment Stack Name and suffix with ```-microchip```.
5. Upload (or drag and drop) the verification certificate.  The
   verification certificate should not have a .json extension.
6. Upload (or drag and drop) the certificate manifest to the S3
   bucket.  On this event, the import begins processing.

The tool begins processing. The certificates and objects are now
created and configured in AWS IoT Core.

# More Implementation Detail

The importer provides three functional components that allows
customization for both the type of hardware security in use and your
product.

- **Supplier Provider**: understands the supplier manifest file
  format. This is the engine that extracts individual certificates and
  stages them for the bulk importer. A different provider may be
  needed for every hardware security component.
- **Product provider**: allows customization for a specific product
  line.  Customization would be required to define properties such as
  individual device Thing Type, Thing Group, and Policy.
- **Bulk import facility**: the bulk importer is comon for all product
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
the importer.  The certificate must be base64 encoded, the default
(and must be unique).

The installation process flow is:

1. Identify or define your supplier manifest provider.
2. Define your product provider.
3. Login to your AWS account.
4. Install the manifest and product provider using CloudFormation.
5. Navigate to the S3 bucket that represents your product.
6. Copy to the S3 bucket the manifest that you want to import.

The basic execution is:

1. The supplier manifest provider separates the certificates from
   other supplier specific metadata and pushes individual SQS
   certificates to a staging S3 bucket.  This bucket serv
2. The product provider listens to the individual certificate staging
   area. For each certificate dropped to the staging area, product
   line specific metadata is applied to a new file, the process
   appends the certificate, and stages the file to the bulk import
   staging area.
3. The bulk import facility listens to files being added to the
   product staging area and performs the API call to import the
   certificate, create any necessary objects (such as Thing), and
   attaches any necessary objects (like Thing Groups, Types, and
   Policies).

# Defining the Product Provider

The Product Provider takes an individual certificate, applies product
specific metadata, and stores the file to a target location used by
the bulk importer.

In the product provider, you define the objects that need to be to be
created for the device the certificate represents as well as making
the appropriate associations.

# Defining the Supplier Provider

The Supplier Provider takes an input dropped to an S3 bucket created by
the deployement process, isolates certificates, and puts certificates
to a target Amazon SQS queue.

# Invoking the Product-Supplier-Importer Installation

The installation expects that you are running on a GNU/Linux based
system. Mileage may vary under Mac OSX.  If your workstation is not a
GNU/Linux variant, it may be best to invoke this process from a
t1.micro Amazon Linux instance in the AWS Cloud.

To invoke the installation, you must perform three steps:

1. Package and build Lambda functions
2. Stage Lambda functions and CloudFormation scripts
3. Invoke the CloudFormation script.


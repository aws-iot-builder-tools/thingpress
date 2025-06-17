# 






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


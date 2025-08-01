# Thingpress

![Coverage](.github/coverage.svg)
![pylint](.github/linting.svg)
![samlint](.github/samlint.svg)
![sambuild](.github/sambuild.svg)

Thingpress is an AWS IoT administration tool. Customers often choose to design IoT devices that have pre-provisioned x.509 certificates. Secure element and trusted platform module manufacturers inject x.509 certificates to these chips in secure manufacturing facilities. The same x.509 certificates must be registered to AWS IoT for devices to authenticate. Thingpress imports these certificates to AWS IoT in a scalable way such that you can import hundreds of thousands, if not millions, of certificates per day.

Thingpress does more than simply import certificates. Devices must be authorized for actions and ideally participate in IoT fleet management. Thingpress automatically creates an AWS IoT Thing in the AWS IoT Registry based on the certificate CN value (common practice). Thingpress optionally attaches AWS IoT Policy (authorization), Thing Type (fleet management), and Thing Group (fleet management). The objects you associate reflect application design and device lifecycle goals. There is more information in the Getting Started section to help guide you.

Thingpress supports manifests from three vendors and programmatically generated certificates. The following is the list
of vendors in alphabetical order, associated pre-provisioned certificate
parts, and Thingpress documentation for each vendor.

| Vendor    | Components | Thingpress<br/>Documentation | 
| --------- | ---------- | ---------------------------- |
| [Espressif Systems](https://www.espressif.com/) | [ESP32-S3](https://www.espressif.com/en/products/socs/esp32-s3) | [Thingpress for Espressif](docs/vendors/espressif.md) |
| [Infineon Technologies SA](https://www.infineon.com/) | [Optiga Trust M Express](https://www.infineon.com/cms/en/product/security-smart-card-solutions/optiga-embedded-security-solutions/optiga-trust/optiga-trust-m-express/)| [Thingpress for Infineon](docs/vendors/infineon.md) |
| [Microchip Technology Inc.](https://www.microchip.com/) | [Trust&Go ATECC608B with TLS](https://www.microchip.com/en-us/products/security/trust-platform/trust-and-go/trust-and-go-tls) | [Thingpress for Microchip](docs/vendors/microchip.md) |
| Generated Certificates | Programmatically generated certificates | [Thingpress for Generated Certificates](docs/vendors/generated.md) |

## Development Roadmap

See our [Development Roadmap](planning/ROADMAP.md) for information about upcoming features and development priorities.

# Getting started

Thingpress is a tool used for production environment preparation.
Careful AWS IoT preparation can provide many benefits throughout
the device lifecycle. At scale (i.e., hundreds of thousands of
devices), adjustments to object attachments (i.e. Thing Group and
Thing Type) can be a daunting task.

1. Familiarize yourself with the following topics:
   [x.509 client certificates](https://docs.aws.amazon.com/iot/latest/developerguide/x509-client-certs.html),
   [AWS IoT Core policies](https://docs.aws.amazon.com/iot/latest/developerguide/iot-policies.html),
   [AWS IoT Things (device registry)](https://docs.aws.amazon.com/iot/latest/developerguide/thing-registry.html), 
   [IoT Thing Types](https://docs.aws.amazon.com/iot/latest/developerguide/thing-types.html), and
   [IoT Thing Group](https://docs.aws.amazon.com/iot/latest/developerguide/thing-groups.html).
2. Become familiar with any planning activity for your chosen vendor: [Espressif](docs/vendors/espressif.md), [Infineon](docs/vendors/infineon.md), [Microchip](docs/vendors/microchip.md), or [Generated Certificates](docs/vendors/generated.md).
3. Evaluate service API call limits. Although Thingpress recovers from
   API throttling to not lose data, avoid API throttling in the
   first place to optimize processing time.
3. Prepare and test artifacts to be associated with the import.
   Verify that the effective policy on the device is exactly what
   want. Policies may be adjusted later, but testing may highlight
   adjustments to Thing Group hierarchies.
4. Install Thingpress with required and vendor specific parameters.
   Multiple Thingpress installations may be required - for example,
   if you have multiple product lines, each having a different
   IoT Thing Type and Group.
5. Invoke the processing by uploading the vendor supplied certificate
   manifest to the vendor specific S3 bucket. Typically, the batch
   speed is approximately 100,000 certificates per hour, including
   all requested object associations.


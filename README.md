# Thingpress

![Coverage](coverage.svg)
![pylint](linting.svg)
![samlint](samlint.svg)
![sambuild](sambuild.svg)

Thingpress is an AWS IoT administration tool. It provides customers who
design-in to their IoT devices a secure element or trusted platform module
that has pre-provisioned certificates. The tool imports certificates
from vendor manifest files that vendors provide alongside the reels of
physical components that manufacturers build into IoT products.

Thingpress does more than simply import certificates. It automatically creates an AWS IoT Thing based on the certificate CN value (common practice) and optionally attaches AWS IoT Policy, Thing Type, and Thing Group. The objects you associate reflect application design and device lifecycle goals. There is more information in the Getting Started section to help guide you.

Thingpress supports manifests from three vendors. The following is the list
of vendors in alphabetical order, associated pre-provisioned certificate
parts, and Thingpress  documentation for each vendor.

| Vendor    | Components | Thingpress<br/>Documentation | 
| --------- | ---------- | ---------------------------- |
| Espressif | ESP32-S3 | [Thingpress for Espressif](doc/espressif.md) |
| Infineon  | Optiga Trust M| [Thingpress for Infineon](doc/infineon.md) |
| Microchip | Trust & Go TLS | [Thingpress for Microchip](doc/microchip.md) |

# Getting started

Thingpress is a tool used for production environment preparation.
Careful AWS IoT preparation can provide many benefits throughout
the device lifecycle. At scale (i.e., hundreds of thousands of
devices), adjustments to object attachments (i.e. Thing Group and
Thing Type) can be a daunting task.

1. Familiarize yourself with the following topics:
   IoT Certificate,
   IoT Policy,
   IoT Thing, 
   IoT Thing Type, and
   IoT Thing Group.
2. Become familiar with any planning activity for your chosen vendor: [Espressif](doc/espressif.md), [Infineon](doc/infineon.md), or [Microchip](doc/microchip.md).
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


# AWS API Limits

Thingpress invokes AWS APIs to import certificates and configurations.

AWS protects customers by setting default limits to APIs. However, high performance operations (like those in Thingpress) may exceed the limits. The following is a list of APIs that may be impacted and to what value may require adjustment.

- [AWS IoT Core endpoints and quotas](https://docs.aws.amazon.com/general/latest/gr/iot-core.html#throttling-limits)

On the AWS IoT Core endpoints and quotas page, use the link in the **Adjustable** column to request an API limit increase.

| API                          | Default Value (TPS) | Adjusted Value (TPS) <br/> (Default Parallelism)|
| ---                          | ------------------- | -------------------- |
| AttachPolicy                 | 15                  | **100** |
| AttachThingPrincipal         | 100                 | n/a |
| AttachThingToThingGroup      | 100                 | n/a |
| CreateThing                  | 100                 | n/a |
| DescribeCertificate          | 10                  | **100** |
| DescribeThing                | 350                 | n/a |
| DescribeThingGroup           | 100                 | n/a |
| DescribeThingType            | 100                 | n/a |
| GetPolicy                    | 10                  | n/a |
| RegisterCertificateWithoutCA | 10                  | **100** |

These limits were last checked on 6/13/2025. Please enter an issue if you identify a discrepancy.

# Thingpress Web Application Specification

## Overview
This document outlines the specifications for a single-page web application that will provide a user interface for the Thingpress IoT certificate management system. The application will allow users to configure AWS IoT settings, upload certificate manifests, and monitor processing status.

## MVP Scope
The Minimum Viable Product (MVP) will focus on:
- Authentication integration with AWS IAM via AWS Amplify
- Basic configuration for AWS IoT settings
- Certificate manifest upload for Infineon vendor type
- Status monitoring and basic dashboard

## User Roles and Permissions

### Admin Role
- Configure AWS IoT Thing Types, Thing Groups, and Thing Policies
- Upload certificate manifests
- View processing status and history
- Manage user access
- Create and manage configuration profiles

### Viewer Role
- View processing status and history of certificate uploads
- View summary statistics/dashboards

## Application Architecture

### Technology Stack
- **Frontend Framework**: React.js
- **State Management**: Redux
- **Authentication**: AWS Amplify
- **Hosting**: AWS Amplify Hosting
- **API Layer**: AWS API Gateway with Lambda functions
- **API Design**: Action-based API endpoints

### UI Components and Layout
Single-page application with the following sections:
1. **Configuration Profiles Section**
   - Save, load, and manage different configurations
   - Configuration parameters include:
     - AWS IoT Thing Type selection
     - AWS IoT Thing Group selection
     - AWS IoT Policy selection
     - Vendor-specific settings

2. **Configuration Section**
   - AWS IoT settings (Thing Types, Thing Groups, Policies)
   - Vendor-specific configuration options

3. **Upload Section**
   - Drag-and-drop interface for certificate manifests
   - For MVP: Focus on Infineon 7z files
   - Certificate bundle type selection (E0E0, E0E1, or E0E2)
   - Upload progress indicators
   - Validation and error handling

4. **Status/History Section**
   - Upload timestamp
   - Vendor type
   - File name
   - Processing status (pending, in progress, completed, failed)
   - Number of certificates processed
   - Success/failure counts
   - Error details (if any)

5. **Dashboard/Statistics Section**
   - Total certificates processed over time (graph)
   - Success/failure rates
   - Processing time statistics
   - Certificates by vendor type (pie chart)
   - Recent activity summary

### API Endpoints

1. **Authentication and User Management**
   - Login/logout
   - User role verification

2. **Configuration Profile Operations**
   - Create profile
   - Read profile
   - Update profile
   - Delete profile
   - List profiles

3. **AWS IoT Resource Operations**
   - Get Thing Types
   - Get Thing Groups
   - Get Policies

4. **Certificate Manifest Upload and Processing**
   - Upload manifest
   - Start processing
   - Cancel processing

5. **Status and History Retrieval**
   - Get processing status
   - Get processing history
   - Get detailed results

6. **Dashboard Statistics and Metrics**
   - Get summary metrics
   - Get time-series data
   - Get vendor distribution

## Development Approach

### Timeline
- MVP development: 2-4 weeks
- Single developer resource

### Methodology
- Agile approach with iterative development
- Minimal upfront documentation
- Regular progress reviews and adjustments

### Testing Strategy
Comprehensive automated testing:
- Unit tests for individual components and functions
- Integration tests for API interactions
- End-to-end tests for critical user flows
- UI component tests

### Deployment Strategy
- Basic CI/CD pipeline using GitHub Actions or AWS CodePipeline
- Automated builds and deployments to AWS Amplify Hosting

### Documentation
Comprehensive documentation including:
- Basic README
- Developer documentation (code comments, setup instructions)
- User documentation (how to use the application)
- Architecture diagrams and technical specifications

## Future Enhancements (Post-MVP)
- Support for additional vendor types (Espressif, Microchip)
- Enhanced dashboard with more analytics
- Batch operations and scheduling
- User management interface
- Advanced configuration options

## Integration with Existing Thingpress System
The web application will integrate with the existing Thingpress serverless architecture by:
1. Using the same S3 buckets for manifest uploads
2. Triggering the same Lambda functions for processing
3. Reading processing status from the same data sources
4. Maintaining compatibility with existing configuration parameters

## Security Considerations
- AWS IAM integration for authentication and authorization
- Secure API access using API Gateway authorization
- HTTPS for all communications
- Input validation for all user inputs
- Proper error handling to prevent information leakage

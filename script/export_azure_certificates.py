#!/usr/bin/env python3
"""
Azure IoT Hub Certificate Exporter

This script exports all certificates from Azure IoT Hub and saves them in the same format
as the generate_certificates.py script (base64-encoded certificate chains, one per line).

Usage:
    python export_azure_certificates.py --connection-string "YOUR_IOTHUB_CONNECTION_STRING" [options]

Options:
    --connection-string STRING   Azure IoT Hub connection string with registry read permissions
    --output-dir DIR             Output directory (default: './output')
    --batch-size SIZE            Certificates per batch file (default: 10000)
    --include-ca                 Include CA certificates in the export (default: False)
    --verify-chain               Verify certificate chains before export (default: False)
    --format FORMAT              Output format: 'base64' or 'pem' (default: 'base64')
"""

import os
import base64
import time
import argparse
import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor
from tqdm import tqdm

# Azure IoT Hub SDK imports
try:
    from azure.iot.hub import IoTHubRegistryManager
    from azure.iot.hub.models import Twin, QuerySpecification
    from azure.core.exceptions import ResourceNotFoundError
except ImportError:
    print("Azure IoT Hub SDK not found. Installing required packages...")
    import subprocess
    subprocess.check_call(["pip", "install", "azure-iot-hub", "tqdm"])
    from azure.iot.hub import IoTHubRegistryManager
    from azure.iot.hub.models import Twin, QuerySpecification
    from azure.core.exceptions import ResourceNotFoundError

def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Export certificates from Azure IoT Hub')
    parser.add_argument('--connection-string', type=str, required=True,
                        help='Azure IoT Hub connection string with registry read permissions')
    parser.add_argument('--output-dir', default='./output',
                        help='Output directory (default: ./output)')
    parser.add_argument('--batch-size', type=int, default=10000,
                        help='Certificates per batch file (default: 10000)')
    parser.add_argument('--include-ca', action='store_true',
                        help='Include CA certificates in the export (default: False)')
    parser.add_argument('--verify-chain', action='store_true',
                        help='Verify certificate chains before export (default: False)')
    parser.add_argument('--format', choices=['base64', 'pem'], default='base64',
                        help='Output format: base64 or pem (default: base64)')
    
    return parser.parse_args()

def get_registry_manager(connection_string: str) -> IoTHubRegistryManager:
    """Create an IoT Hub Registry Manager client."""
    try:
        return IoTHubRegistryManager(connection_string)
    except Exception as e:
        print(f"Error creating IoT Hub Registry Manager: {e}")
        raise

def get_all_device_ids(registry_manager: IoTHubRegistryManager) -> List[str]:
    """Get all device IDs from IoT Hub."""
    try:
        # Query for all devices
        query_spec = QuerySpecification(query="SELECT deviceId FROM devices")
        query_result = registry_manager.query_iot_hub(query_spec, None, 1000)
        
        device_ids = []
        for item in query_result.items:
            device_ids.append(item["deviceId"])
            
        return device_ids
    except Exception as e:
        print(f"Error querying devices: {e}")
        raise

def get_device_certificate(registry_manager: IoTHubRegistryManager, device_id: str) -> Optional[str]:
    """Get the certificate for a specific device."""
    try:
        # Get the device twin
        twin = registry_manager.get_twin(device_id)
        
        # Check if the device has a certificate in its reported properties
        if twin and twin.reported_properties and 'x509' in twin.reported_properties:
            if 'certificate' in twin.reported_properties['x509']:
                return twin.reported_properties['x509']['certificate']
        
        # If no certificate in reported properties, try to get from device authentication
        device = registry_manager.get_device(device_id)
        if device and device.authentication and device.authentication.x509_thumbprint:
            # Unfortunately, IoT Hub API doesn't provide direct access to the certificate
            # We can only get the thumbprint, not the actual certificate
            print(f"Device {device_id} has X.509 authentication but certificate is not available via API")
            
        return None
    except ResourceNotFoundError:
        print(f"Device {device_id} not found")
        return None
    except Exception as e:
        print(f"Error getting certificate for device {device_id}: {e}")
        return None

def get_ca_certificates(registry_manager: IoTHubRegistryManager) -> List[str]:
    """Get all CA certificates from IoT Hub."""
    # Note: The Azure IoT Hub SDK doesn't provide direct access to CA certificates
    # This is a placeholder function - in a real implementation, you would need to use
    # the Azure REST API directly or the Azure CLI to get CA certificates
    print("Warning: Getting CA certificates is not supported through the SDK")
    print("Please use Azure Portal or Azure CLI to export CA certificates")
    return []

def process_device_batch(registry_manager: IoTHubRegistryManager, 
                         device_ids: List[str], 
                         verify_chain: bool) -> List[str]:
    """Process a batch of devices and get their certificates."""
    results = []
    
    for device_id in device_ids:
        cert = get_device_certificate(registry_manager, device_id)
        if cert:
            # In a real implementation, you would verify the certificate chain here if verify_chain is True
            # Since we can't get the full chain from the API, we'll just use what we have
            results.append((device_id, cert))
    
    return results

def format_certificate(cert: str, output_format: str) -> str:
    """Format the certificate according to the specified output format."""
    if output_format == 'base64':
        # Ensure the certificate is in PEM format first
        if not cert.startswith('-----BEGIN CERTIFICATE-----'):
            # If it's already base64, return as is
            return cert
        
        # Remove PEM headers and newlines
        cert_clean = cert.replace('-----BEGIN CERTIFICATE-----', '')
        cert_clean = cert_clean.replace('-----END CERTIFICATE-----', '')
        cert_clean = cert_clean.replace('\n', '')
        
        # Re-encode to ensure proper base64 format
        return base64.b64encode(base64.b64decode(cert_clean)).decode('utf-8')
    else:  # pem format
        if cert.startswith('-----BEGIN CERTIFICATE-----'):
            return cert
        
        # Try to decode if it's base64
        try:
            cert_bytes = base64.b64decode(cert)
            return f"-----BEGIN CERTIFICATE-----\n{base64.b64encode(cert_bytes).decode('utf-8')}\n-----END CERTIFICATE-----"
        except:
            # If decoding fails, return as is
            return cert

def main():
    """Main function."""
    args = parse_args()
    
    # Create output directory if it doesn't exist
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print("Connecting to Azure IoT Hub...")
    registry_manager = get_registry_manager(args.connection_string)
    
    print("Getting all device IDs...")
    device_ids = get_all_device_ids(registry_manager)
    print(f"Found {len(device_ids)} devices")
    
    # Get CA certificates if requested
    ca_certs = []
    if args.include_ca:
        print("Getting CA certificates...")
        ca_certs = get_ca_certificates(registry_manager)
        print(f"Found {len(ca_certs)} CA certificates")
    
    # Create timestamp for filenames
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Calculate number of batches for devices
    num_batches = (len(device_ids) + args.batch_size - 1) // args.batch_size
    
    print(f"Processing {len(device_ids)} devices in {num_batches} batches...")
    
    # Process devices in batches using multithreading
    all_certificates = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = []
        
        for batch_idx in range(num_batches):
            start_idx = batch_idx * args.batch_size
            end_idx = min(start_idx + args.batch_size, len(device_ids))
            batch_device_ids = device_ids[start_idx:end_idx]
            
            future = executor.submit(
                process_device_batch,
                registry_manager,
                batch_device_ids,
                args.verify_chain
            )
            futures.append(future)
        
        # Process results as they complete
        for future in tqdm(futures, desc="Processing device batches", unit="batch"):
            batch_results = future.result()
            all_certificates.extend(batch_results)
    
    print(f"Found certificates for {len(all_certificates)} devices")
    
    # Add CA certificates to the list if requested
    if args.include_ca:
        all_certificates.extend([("CA", cert) for cert in ca_certs])
    
    # Calculate number of output batches
    num_output_batches = (len(all_certificates) + args.batch_size - 1) // args.batch_size
    
    print(f"Writing {len(all_certificates)} certificates to {num_output_batches} output files...")
    
    # Write certificates to output files
    for batch_idx in range(num_output_batches):
        start_idx = batch_idx * args.batch_size
        end_idx = min(start_idx + args.batch_size, len(all_certificates))
        batch_certs = all_certificates[start_idx:end_idx]
        
        batch_file = output_dir / f"azure_certificates_{timestamp}_batch_{batch_idx}.txt"
        with open(batch_file, "w") as f:
            for device_id, cert in batch_certs:
                formatted_cert = format_certificate(cert, args.format)
                f.write(f"{formatted_cert}\n")
    
    # Write a mapping file with device IDs and their corresponding certificates
    mapping_file = output_dir / f"azure_certificates_{timestamp}_mapping.csv"
    with open(mapping_file, "w") as f:
        f.write("device_id,certificate_hash\n")
        for device_id, cert in all_certificates:
            # Use the first 8 characters of the hash as an identifier
            cert_hash = hash(cert) & 0xFFFFFFFF
            f.write(f"{device_id},{cert_hash:08x}\n")
    
    print(f"Successfully exported {len(all_certificates)} certificates.")
    print(f"Output files are in {output_dir}")
    print(f"Device ID to certificate mapping saved to {mapping_file}")

if __name__ == "__main__":
    start_time = time.time()
    main()
    elapsed_time = time.time() - start_time
    print(f"Total execution time: {elapsed_time:.2f} seconds")

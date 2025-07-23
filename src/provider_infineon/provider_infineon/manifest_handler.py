"""
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""
import io

import py7zr
import py7zr.io as py7io
from boto3 import Session
from layer_utils.aws_utils import s3_object_bytes
from layer_utils.cert_utils import format_certificate, get_cn
from layer_utils.throttling_utils import create_standardized_throttler

default_session: Session = Session()

def verify_certtype(option: str) -> bool:
    """ Check type selection for import """
    match option:
        case "E0E0":
            return True
        case "E0E1":
            return True
        case "E0E2":
            return True
        case _:
            raise ValueError("Bad cert type code.")

def verify_certificate_set(files: list[py7zr.FileInfo], option: str) -> str:
    """Ensure that the bundlke exists in the payload"""
    if verify_certtype(option) is False or files is None:
        return None
    p = f"_{option}_Certs.7z"
    for x in files:
        if p in x.filename:
            return x.filename
    return None

def select_certificate_set(manifest_bundle: io.BytesIO, option: str) -> io.BytesIO:
    """There are 3 bundles within the main payload, select which one of it exists."""
    szf = py7zr.SevenZipFile(manifest_bundle)
    f = verify_certificate_set(szf.list(), option)
    if f is None:
        raise FileNotFoundError("file having option not found ")
    # get single file from bundle, return as io,BytesIO
    fcty = py7io.BytesIOFactory(limit=10)
    szf.extract(factory=fcty)
    return io.BytesIO(fcty.get(filename = f).read())

def send_certificates(manifest_archive: io.BytesIO,
                      config: dict,
                      queue_url: str,
                      session: Session) -> int:
    "Routine to send data through queue for further processing with batch optimization."

    # Process certificates in batches for optimal SQS throughput
    batch_messages = []
    batch_size = 10  # SQS batch limit
    total_count = 0

    # Initialize standardized throttler
    throttler = create_standardized_throttler()

    szf = py7zr.SevenZipFile(manifest_archive)
    fcty = py7io.BytesIOFactory(limit=10000)
    szf.extract(factory=fcty)

    for x in szf.list():
        j = fcty.get(filename = x.filename).read().decode('ascii')
        k = format_certificate(j)
        l = get_cn(j)

        cert_config = config.copy()
        cert_config['thing'] = l
        cert_config['certificate'] = k

        batch_messages.append(cert_config)
        total_count += 1

        # Send batch when full
        if len(batch_messages) >= batch_size:
            throttler.send_batch_with_throttling(batch_messages, queue_url, session)
            batch_messages = []

    # Send remaining messages
    if batch_messages:
        throttler.send_batch_with_throttling(
            batch_messages, queue_url, session, is_final_batch=True)

    return total_count

def invoke_export(config, queue_url, cert_type, session: Session=default_session):
    """
    The manifest_file must be a file-like object
    Main interface to invoke manifest processing routines
    """
    manifest_bytes = s3_object_bytes(config['bucket'],
                                    config['key'],
                                    getvalue=False,
                                    session=session)
    x = select_certificate_set(manifest_bytes, cert_type)
    return send_certificates(x, config, queue_url=queue_url, session=session)

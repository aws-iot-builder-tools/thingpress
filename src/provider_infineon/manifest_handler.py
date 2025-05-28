"""
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""
import io
import py7zr
import py7zr.io as py7io
from cert_utils import format_certificate, get_cn
from aws_utils import queue_manifest_certificate

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
            return False

def verify_certificate_set(files: list[py7zr.FileInfo], option: str) -> str:
    if verify_certtype(option) is False or files is None:
        return None
    p = f"_{option}_Certs.7z"
    for x in files:
        if p in x.filename:
            return x.filename
    return None

def select_certificate_set(manifest_bundle: io.BytesIO, option: str) -> io.BytesIO:
    szf = py7zr.SevenZipFile(manifest_bundle)
    f = verify_certificate_set(szf.list(), option)
    if f is None:
        raise FileNotFoundError("file having option not found ")
    # get single file from bundle, return as io,BytesIO
    fcty = py7io.BytesIOFactory(limit=10)
    szf.extract(factory=fcty)
    return io.BytesIO(fcty.get(filename = f).read())

def send_certificates(manifest_archive: io.BytesIO, queue_url: str):
    szf = py7zr.SevenZipFile(manifest_archive)
    fcty = py7io.BytesIOFactory(limit=10000)
    szf.extract(factory=fcty)
    for x in szf.list():
        j = fcty.get(filename = x.filename).read().decode('ascii')
        k = format_certificate(j)
        l = get_cn(j)
        queue_manifest_certificate(identity=l,
                                   certificate=k,
                                   queue_url=queue_url)

def invoke_export(manifest_file, queue_url):
    pass


# There are 3 files of importance:
# *_E0E0_Certs.7z
# *_E0E1_Certs.7z
# *_E0E2_Certs.7z
#
# any combination may be imported.
# 
# Certificate has filename format as:
# <serial>_E0E0.pem
#
# By default, thing name will be serial number.
# 
# 1/ drop in full 7z which will have file format like:
# 78211223032C7EFA_b41425b9-b42b-47fd-95c2-f981b4c61561_v1.0.7z
#
# 2/ extract file of type chosen (E0E0/E0E1/E0E2)
#  # size ranges ~55kb - ~140kb
# 
# 3/ list files and perform extraction operation on each one.

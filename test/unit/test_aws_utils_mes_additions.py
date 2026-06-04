"""
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

Unit tests for MES two-phase provisioning additions to aws_utils
"""
import os
import base64
from unittest import TestCase
from pytest import raises
from moto import mock_aws
from botocore.exceptions import ClientError
from boto3 import _get_default_session
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization

from layer_utils.aws_utils import (
    validate_and_get_certificate,
    activate_certificate,
    process_thing_attributes,
    register_certificate
)
from layer_utils.cert_utils import decode_certificate
from layer_utils.circuit_state import clear_circuits

# Ensure that we are not using real AWS credentials
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
os.environ["AWS_REGION"] = "us-east-1"
os.environ["AWS_ACCESS_KEY_ID"] = "testing"
os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
os.environ["AWS_SECURITY_TOKEN"] = "testing"
os.environ["AWS_SESSION_TOKEN"] = "testing"


@mock_aws(config={
    "core": {
        "mock_credentials": True,
        "reset_boto3_session": False,
        "service_whitelist": None,
    },
    'iot': {'use_valid_cert': True}
})
class TestAwsUtilsMesAdditions(TestCase):
    """Unit tests for MES two-phase provisioning functions"""

    def setUp(self):
        clear_circuits()
        self.session = _get_default_session()

        # Load test certificate following the pattern from test_aws_utils.py
        with open('./test/artifacts/single.pem', 'rb') as data:
            pem_obj = x509.load_pem_x509_certificate(data.read(), backend=default_backend())
            block = pem_obj.public_bytes(encoding=serialization.Encoding.PEM).decode('ascii')
            local_cert_loaded = str(base64.b64encode(block.encode('ascii')))

        # Decode it for use with register_certificate
        self.decoded_cert = decode_certificate(local_cert_loaded)

    def test_register_certificate_with_active_status(self):
        """Test register_certificate with ACTIVE status (default)"""
        cert_id = register_certificate(self.decoded_cert, status='ACTIVE', session=self.session)

        # Verify certificate was registered
        assert cert_id is not None

        # Verify status is ACTIVE
        iot_client = self.session.client('iot')
        response = iot_client.describe_certificate(certificateId=cert_id)
        assert response['certificateDescription']['status'] == 'ACTIVE'

    def test_register_certificate_with_inactive_status(self):
        """Test register_certificate with INACTIVE status"""
        cert_id = register_certificate(
            self.decoded_cert,
            status='INACTIVE',
            session=self.session
        )

        # Verify certificate was registered
        assert cert_id is not None

        # Verify status is INACTIVE
        iot_client = self.session.client('iot')
        response = iot_client.describe_certificate(certificateId=cert_id)
        assert response['certificateDescription']['status'] == 'INACTIVE'

    def test_validate_and_get_certificate_success(self):
        """Test validate_and_get_certificate with valid fingerprint"""
        # First register a certificate
        cert_id = register_certificate(self.decoded_cert, session=self.session)

        # Now validate and get it
        cert_info = validate_and_get_certificate(cert_id, session=self.session)

        assert cert_info['certificate_id'] == cert_id
        assert cert_info['certificate_arn'] is not None
        assert cert_info['status'] == 'ACTIVE'

    def test_validate_and_get_certificate_invalid_format(self):
        """Test validate_and_get_certificate with invalid fingerprint format"""
        with raises(ValueError) as exc:
            validate_and_get_certificate("invalid-fingerprint", session=self.session)

        assert "Invalid certificate fingerprint format" in str(exc.value)

    def test_validate_and_get_certificate_not_found(self):
        """Test validate_and_get_certificate with non-existent certificate"""
        # Valid format but doesn't exist
        fake_fingerprint = "a" * 64

        with raises(ClientError):
            validate_and_get_certificate(fake_fingerprint, session=self.session)

    def test_activate_certificate_from_inactive(self):
        """Test activate_certificate changes INACTIVE to ACTIVE"""
        # Register certificate with INACTIVE status
        cert_id = register_certificate(
            self.decoded_cert,
            status='INACTIVE',
            session=self.session
        )

        # Activate it
        result = activate_certificate(cert_id, session=self.session)
        assert result == cert_id

        # Verify status changed to ACTIVE
        iot_client = self.session.client('iot')
        response = iot_client.describe_certificate(certificateId=cert_id)
        assert response['certificateDescription']['status'] == 'ACTIVE'

    def test_activate_certificate_already_active(self):
        """Test activate_certificate is idempotent (already ACTIVE)"""
        # Register certificate with ACTIVE status
        cert_id = register_certificate(self.decoded_cert, status='ACTIVE', session=self.session)

        # Try to activate (should be no-op)
        result = activate_certificate(cert_id, session=self.session)
        assert result == cert_id

        # Verify still ACTIVE
        iot_client = self.session.client('iot')
        response = iot_client.describe_certificate(certificateId=cert_id)
        assert response['certificateDescription']['status'] == 'ACTIVE'

    def test_process_thing_attributes_success(self):
        """Test process_thing_attributes sets attributes correctly"""
        # Create a Thing first
        thing_name = "test-thing-with-attributes"
        iot_client = self.session.client('iot')
        iot_client.create_thing(thingName=thing_name)

        # Set attributes
        attributes = {
            'DSN': 'DSN123456',
            'MAC': 'AA:BB:CC:DD:EE:FF',
            'FirmwareVersion': '1.0.0'
        }

        process_thing_attributes(thing_name, attributes, session=self.session)

        # Verify attributes were set
        response = iot_client.describe_thing(thingName=thing_name)
        assert response['attributes'] == attributes

    def test_process_thing_attributes_empty(self):
        """Test process_thing_attributes with empty attributes (no-op)"""
        thing_name = "test-thing-empty-attrs"
        iot_client = self.session.client('iot')
        iot_client.create_thing(thingName=thing_name)

        # Should not raise error
        process_thing_attributes(thing_name, {}, session=self.session)

    def test_process_thing_attributes_too_many(self):
        """Test process_thing_attributes validates attribute count"""
        thing_name = "test-thing-too-many"

        # Create 51 attributes (exceeds limit of 50)
        attributes = {f'attr{i}': f'value{i}' for i in range(51)}

        with raises(ValueError) as exc:
            process_thing_attributes(thing_name, attributes, session=self.session)

        assert "Too many attributes" in str(exc.value)

    def test_process_thing_attributes_key_too_long(self):
        """Test process_thing_attributes validates key length"""
        thing_name = "test-thing-long-key"

        # Key longer than 128 characters
        attributes = {'a' * 129: 'value'}

        with raises(ValueError) as exc:
            process_thing_attributes(thing_name, attributes, session=self.session)

        assert "Attribute key too long" in str(exc.value)

    def test_process_thing_attributes_value_too_long(self):
        """Test process_thing_attributes validates value length"""
        thing_name = "test-thing-long-value"

        # Value longer than 800 characters
        attributes = {'key': 'v' * 801}

        with raises(ValueError) as exc:
            process_thing_attributes(thing_name, attributes, session=self.session)

        assert "Attribute value too long" in str(exc.value)

    def test_process_thing_attributes_non_string_value(self):
        """Test process_thing_attributes validates value type"""
        thing_name = "test-thing-non-string"

        # Non-string value
        attributes = {'key': 123}

        with raises(ValueError) as exc:
            process_thing_attributes(thing_name, attributes, session=self.session)

        assert "Attribute value must be string" in str(exc.value)

from __future__ import unicode_literals

import os

from django.conf import settings
from django.core.files.base import File
from django.test import TestCase

from documents.models import DocumentType
from documents.test_models import TEST_DOCUMENT_PATH, TEST_DOCUMENT_TYPE
from django_gpg.literals import SIGNATURE_STATE_VALID
from django_gpg.runtime import gpg

from .models import DocumentVersionSignature

TEST_SIGNED_DOCUMENT_PATH = os.path.join(settings.BASE_DIR, 'contrib', 'sample_documents', 'mayan_11_1.pdf.gpg')
TEST_SIGNATURE_FILE_PATH = os.path.join(settings.BASE_DIR, 'contrib', 'sample_documents', 'mayan_11_1.pdf.sig')
TEST_KEY_FILE = os.path.join(settings.BASE_DIR, 'contrib', 'sample_documents', 'key0x5F3F7F75D210724D.asc')


class DocumentTestCase(TestCase):
    def setUp(self):
        self.document_type = DocumentType.objects.create(label=TEST_DOCUMENT_TYPE)

        ocr_settings = self.document_type.ocr_settings
        ocr_settings.auto_ocr = False
        ocr_settings.save()

        with open(TEST_DOCUMENT_PATH) as file_object:
            self.document = self.document_type.new_document(file_object=File(file_object), label='mayan_11_1.pdf')

        with open(TEST_KEY_FILE) as file_object:
            gpg.import_key(file_object.read())

    def test_document_no_signature(self):
        self.assertEqual(DocumentVersionSignature.objects.has_detached_signature(self.document.latest_version), False)

    def test_new_document_version_signed(self):
        with open(TEST_SIGNED_DOCUMENT_PATH) as file_object:
            self.document.new_version(file_object=File(file_object), comment='test comment 1')

        self.assertEqual(DocumentVersionSignature.objects.has_detached_signature(self.document.latest_version), False)
        self.assertEqual(DocumentVersionSignature.objects.verify_signature(self.document.latest_version).status, SIGNATURE_STATE_VALID)

    def test_detached_signatures(self):
        with open(TEST_DOCUMENT_PATH) as file_object:
            self.document.new_version(file_object=File(file_object), comment='test comment 2')

        # GPGVerificationError
        self.assertEqual(DocumentVersionSignature.objects.verify_signature(self.document.latest_version), None)

        with open(TEST_SIGNATURE_FILE_PATH, 'rb') as file_object:
            DocumentVersionSignature.objects.add_detached_signature(self.document.latest_version, File(file_object))

        self.assertEqual(DocumentVersionSignature.objects.has_detached_signature(self.document.latest_version), True)
        self.assertEqual(DocumentVersionSignature.objects.verify_signature(self.document.latest_version).status, SIGNATURE_STATE_VALID)

    def tearDown(self):
        self.document.delete()
        self.document_type.delete()

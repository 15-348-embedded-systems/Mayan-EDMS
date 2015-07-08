from __future__ import unicode_literals

import shutil
import tempfile

from django.contrib.auth.models import User
from django.core.urlresolvers import reverse
from django.test.client import Client
from django.test import TestCase

from documents.models import Document, DocumentType
from sources.literals import SOURCE_CHOICE_WEB_FORM
from sources.models import WebFormSource

from documents.tests import (
    TEST_ADMIN_PASSWORD, TEST_ADMIN_USERNAME, TEST_ADMIN_EMAIL,
    TEST_DOCUMENT_PATH, TEST_SMALL_DOCUMENT_PATH,
    TEST_DOCUMENT_DESCRIPTION, TEST_DOCUMENT_TYPE,
    TEST_NON_ASCII_DOCUMENT_FILENAME, TEST_NON_ASCII_DOCUMENT_PATH,
    TEST_NON_ASCII_COMPRESSED_DOCUMENT_PATH
)

from .literals import SOURCE_UNCOMPRESS_CHOICE_N, SOURCE_UNCOMPRESS_CHOICE_Y
from .models import WatchFolderSource


class UploadDocumentTestCase(TestCase):
    """
    Test creating documents
    """

    def setUp(self):
        self.document_type = DocumentType.objects.create(label=TEST_DOCUMENT_TYPE)
        ocr_settings = self.document_type.ocr_settings
        ocr_settings.auto_ocr = False
        ocr_settings.save()

        self.admin_user = User.objects.create_superuser(username=TEST_ADMIN_USERNAME, email=TEST_ADMIN_EMAIL, password=TEST_ADMIN_PASSWORD)
        self.client = Client()

    def test_upload_a_document(self):
        # Login the admin user
        logged_in = self.client.login(username=TEST_ADMIN_USERNAME, password=TEST_ADMIN_PASSWORD)
        self.assertTrue(logged_in)
        self.assertTrue(self.admin_user.is_authenticated())

        # Create new webform source
        self.client.post(reverse('sources:setup_source_create', args=[SOURCE_CHOICE_WEB_FORM]), {'label': 'test', 'uncompress': 'n', 'enabled': True})
        self.assertEqual(WebFormSource.objects.count(), 1)

        # Upload the test document
        with open(TEST_DOCUMENT_PATH) as file_descriptor:
            self.client.post(reverse('sources:upload_interactive'), {'document-language': 'eng', 'source-file': file_descriptor, 'document_type_id': self.document_type.pk, 'label': 'mayan_11_1.pdf'})
        self.assertEqual(Document.objects.count(), 1)

        self.document = Document.objects.all().first()
        self.failUnlessEqual(self.document.exists(), True)
        self.failUnlessEqual(self.document.size, 272213)

        self.failUnlessEqual(self.document.file_mimetype, 'application/pdf')
        self.failUnlessEqual(self.document.file_mime_encoding, 'binary')
        self.failUnlessEqual(self.document.label, 'mayan_11_1.pdf')
        self.failUnlessEqual(self.document.checksum, 'c637ffab6b8bb026ed3784afdb07663fddc60099853fae2be93890852a69ecf3')
        self.failUnlessEqual(self.document.page_count, 47)

        # Delete the document
        self.client.post(reverse('documents:document_delete', args=[self.document.pk]))
        self.assertEqual(Document.objects.count(), 0)

    def test_issue_25(self):
        # Login the admin user
        logged_in = self.client.login(username=TEST_ADMIN_USERNAME, password=TEST_ADMIN_PASSWORD)
        self.assertTrue(logged_in)
        self.assertTrue(self.admin_user.is_authenticated())

        # Create new webform source
        self.client.post(reverse('sources:setup_source_create', args=[SOURCE_CHOICE_WEB_FORM]), {'label': 'test', 'uncompress': 'n', 'enabled': True})
        self.assertEqual(WebFormSource.objects.count(), 1)

        # Upload the test document
        with open(TEST_SMALL_DOCUMENT_PATH) as file_descriptor:
            self.client.post(reverse('sources:upload_interactive'), {'document-language': 'eng', 'source-file': file_descriptor, 'document_type_id': self.document_type.pk})
        self.assertEqual(Document.objects.count(), 1)

        document = Document.objects.first()
        # Test for issue 25 during creation
        # ** description fields was removed from upload from **
        self.failUnlessEqual(document.description, '')

        # Reset description
        document.description = TEST_DOCUMENT_DESCRIPTION
        document.save()
        self.failUnlessEqual(document.description, TEST_DOCUMENT_DESCRIPTION)

        # Test for issue 25 during editing
        self.client.post(reverse('documents:document_edit', args=[document.pk]), {'description': TEST_DOCUMENT_DESCRIPTION, 'language': document.language, 'label': document.label})
        # Fetch document again and test description
        document = Document.objects.first()
        self.failUnlessEqual(document.description, TEST_DOCUMENT_DESCRIPTION)

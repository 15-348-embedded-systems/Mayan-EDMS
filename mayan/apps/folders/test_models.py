from __future__ import unicode_literals

import os

from django.conf import settings
from django.contrib.auth.models import User
from django.core.files.base import File
from django.test import TestCase

from authentication.tests import (
    TEST_ADMIN_EMAIL, TEST_ADMIN_PASSWORD, TEST_ADMIN_USERNAME
)
from documents.models import Document, DocumentType
from documents.test_models import TEST_DOCUMENT_TYPE

from .models import Folder

TEST_DOCUMENT_PATH = os.path.join(settings.BASE_DIR, 'contrib', 'sample_documents', 'title_page.png')


class FolderTestCase(TestCase):
    def setUp(self):
        self.document_type = DocumentType.objects.create(label=TEST_DOCUMENT_TYPE)

        with open(TEST_DOCUMENT_PATH) as file_object:
            self.document = self.document_type.new_document(file_object=File(file_object))

        self.user = User.objects.create_superuser(username=TEST_ADMIN_USERNAME, email=TEST_ADMIN_EMAIL, password=TEST_ADMIN_PASSWORD)

    def test_creation_of_folder(self):
        folder = Folder.objects.create(label='test', user=self.user)

        self.assertEqual(Folder.objects.all().count(), 1)
        self.assertEqual(list(Folder.objects.all()), [folder])
        folder.delete()

    def test_addition_of_documents(self):
        user = User.objects.all()[0]
        folder = Folder.objects.create(label='test', user=self.user)
        folder.documents.add(self.document)

        self.assertEqual(folder.documents.count(), 1)
        self.assertEqual(list(folder.documents.all()), [self.document])
        folder.delete()

    def test_addition_and_deletion_of_documents(self):
        user = User.objects.all()[0]
        folder = Folder.objects.create(label='test', user=self.user)
        folder.documents.add(self.document)

        self.assertEqual(folder.documents.count(), 1)
        self.assertEqual(list(folder.documents.all()), [self.document])

        folder.documents.remove(self.document)

        self.assertEqual(folder.documents.count(), 0)
        self.assertEqual(list(folder.documents.all()), [])

        folder.delete()

    def tearDown(self):
        self.document.delete()
        self.document_type.delete()

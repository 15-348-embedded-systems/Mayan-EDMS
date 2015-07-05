from __future__ import unicode_literals

import base64
import hashlib
import logging
import os
import uuid

from django.contrib.auth.models import User
from django.core.urlresolvers import reverse
from django.db import models, transaction
from django.utils.encoding import python_2_unicode_compatible
from django.utils.timezone import now
from django.utils.translation import ugettext_lazy as _

from celery.execute import send_task

from common.literals import TIME_DELTA_UNIT_CHOICES
from common.models import SharedUploadedFile
from common.settings import setting_temporary_directory
from common.utils import fs_cleanup
from converter import (
    converter_class, TransformationResize, TransformationRotate,
    TransformationZoom
)
from converter.exceptions import InvalidOfficeFormat, UnknownFileFormat
from converter.literals import DEFAULT_ZOOM_LEVEL, DEFAULT_ROTATION
from converter.models import Transformation
from mimetype.api import get_mimetype

from .events import (
    event_document_create, event_document_new_version,
    event_document_version_revert
)
from .literals import DEFAULT_DELETE_PERIOD, DEFAULT_DELETE_TIME_UNIT
from .managers import (
    DocumentManager, DocumentTypeManager, PassthroughManager,
    RecentDocumentManager, TrashCanManager
)
from .runtime import storage_backend
from .settings import (
    setting_cache_path, setting_display_size, setting_language,
    setting_language_choices, setting_zoom_max_level, setting_zoom_min_level
)
from .signals import (
    post_document_created, post_document_type_change, post_version_upload
)

HASH_FUNCTION = lambda x: hashlib.sha256(x).hexdigest()  # document image cache name hash function
logger = logging.getLogger(__name__)


def UUID_FUNCTION(*args, **kwargs):
    return unicode(uuid.uuid4())


@python_2_unicode_compatible
class DocumentType(models.Model):
    """
    Define document types or classes to which a specific set of
    properties can be attached
    """
    name = models.CharField(max_length=32, unique=True, verbose_name=_('Name'))
    trash_time_period = models.PositiveIntegerField(blank=True, help_text=_('Amount of time after which documents of this type will be moved to the trash.'), null=True, verbose_name=_('Trash time period'))
    trash_time_unit = models.CharField(blank=True, choices=TIME_DELTA_UNIT_CHOICES, null=True, max_length=8, verbose_name=_('Trash time unit'))
    delete_time_period = models.PositiveIntegerField(default=DEFAULT_DELETE_PERIOD, help_text=_('Amount of time after which documents of this type in the trash will be deleted.'), verbose_name=_('Delete time period'))
    delete_time_unit = models.CharField(choices=TIME_DELTA_UNIT_CHOICES, default=DEFAULT_DELETE_TIME_UNIT, max_length=8, verbose_name=_('Delete time unit'))

    objects = DocumentTypeManager()

    def __str__(self):
        return self.name

    def natural_key(self):
        return (self.name,)

    def new_document(self, file_object, label=None, description=None, language=None, _user=None):
        if not language:
            language = setting_language.value

        if not label:
            label = unicode(file_object)

        document = self.documents.create(description=description, language=language, label=label)
        document.save(_user=_user)

        document.new_version(file_object=file_object, _user=_user)

        return document

    @transaction.atomic
    def upload_single_document(self, document_type, file_object, label=None, description=None, language=None, user=None):
        document = self.model(description=description, document_type=document_type, language=language, label=label or unicode(file_object))
        document.save(user=user)
        version = document.new_version(file_object=file_object, user=user)
        document.set_document_type(document_type, force=True)
        return version

    class Meta:
        verbose_name = _('Document type')
        verbose_name_plural = _('Documents types')
        ordering = ('name',)


@python_2_unicode_compatible
class Document(models.Model):
    """
    Defines a single document with it's fields and properties
    """

    uuid = models.CharField(default=UUID_FUNCTION, max_length=48, editable=False)
    document_type = models.ForeignKey(DocumentType, verbose_name=_('Document type'), related_name='documents')
    label = models.CharField(max_length=255, default=_('Uninitialized document'), db_index=True, help_text=_('The name of the document'), verbose_name=_('Label'))
    description = models.TextField(blank=True, null=True, verbose_name=_('Description'))
    date_added = models.DateTimeField(verbose_name=_('Added'), auto_now_add=True)
    language = models.CharField(choices=setting_language_choices.value, default=setting_language.value, max_length=8, verbose_name=_('Language'))
    in_trash = models.BooleanField(default=False, editable=False, verbose_name=_('In trash?'))
    deleted_date_time = models.DateTimeField(blank=True, editable=True, null=True, verbose_name=_('Date and time trashed'))
    is_stub = models.BooleanField(default=True, editable=False, verbose_name=_('Is stub?'))

    objects = DocumentManager()
    passthrough = PassthroughManager()
    trash = TrashCanManager()

    class Meta:
        verbose_name = _('Document')
        verbose_name_plural = _('Documents')
        ordering = ('-date_added',)

    def set_document_type(self, document_type, force=False):
        has_changed = self.document_type != document_type

        self.document_type = document_type
        self.save()
        if has_changed or force:
            post_document_type_change.send(sender=self.__class__, instance=self)

    def invalidate_cache(self):
        for document_version in self.versions.all():
            document_version.invalidate_cache()

    def __str__(self):
        return self.label

    def get_absolute_url(self):
        return reverse('documents:document_preview', args=[self.pk])

    def save(self, *args, **kwargs):
        user = kwargs.pop('_user', None)
        new_document = not self.pk
        super(Document, self).save(*args, **kwargs)

        if new_document:
            if user:
                self.add_as_recent_document_for_user(user)
                event_document_create.commit(actor=user, target=self)
            else:
                event_document_create.commit(target=self)

    def add_as_recent_document_for_user(self, user):
        RecentDocument.objects.add_document_for_user(user, self)

    def delete(self, *args, **kwargs):
        if not self.in_trash and kwargs.get('to_trash', True):
            self.in_trash = True
            self.deleted_date_time = now()
            self.save()
        else:
            for version in self.versions.all():
                version.delete()

            return super(Document, self).delete(*args, **kwargs)

    def restore(self):
        self.in_trash = False
        self.save()

    @property
    def size(self):
        return self.latest_version.size

    def new_version(self, file_object, comment=None, _user=None):
        from .tasks import task_upload_new_version

        logger.info('Queueing creation of a new document version for document: %s', self)

        shared_uploaded_file = SharedUploadedFile.objects.create(file=file_object)

        if _user:
            user_id = _user.pk
        else:
            user_id = None

        task_upload_new_version.apply_async(kwargs=dict(
            shared_uploaded_file_id=shared_uploaded_file.pk,
            document_id=self.pk, user_id=user_id,
        ), queue='uploads')

        logger.info('New document version queued for document: %s', self)

    # Proxy methods
    def open(self, *args, **kwargs):
        """
        Return a file descriptor to a document's file irrespective of
        the storage backend
        """
        return self.latest_version.open(*args, **kwargs)

    def save_to_file(self, *args, **kwargs):
        return self.latest_version.save_to_file(*args, **kwargs)

    def exists(self):
        """
        Returns a boolean value that indicates if the document's
        latest version file exists in storage
        """
        return self.latest_version.exists()

    # Compatibility methods
    @property
    def file(self):
        return self.latest_version.file

    @property
    def file_mimetype(self):
        return self.latest_version.mimetype

    # TODO: rename to file_encoding
    @property
    def file_mime_encoding(self):
        return self.latest_version.encoding

    @property
    def date_updated(self):
        return self.latest_version.timestamp

    @property
    def checksum(self):
        return self.latest_version.checksum

    @property
    def signature_state(self):
        return self.latest_version.signature_state

    @property
    def pages(self):
        try:
            return self.latest_version.pages
        except AttributeError:
            # Document has no version yet
            return 0

    @property
    def page_count(self):
        return self.latest_version.page_count

    @property
    def latest_version(self):
        return self.versions.order_by('timestamp').last()

    def document_save_to_temp_dir(self, filename, buffer_size=1024 * 1024):
        temporary_path = os.path.join(setting_temporary_directory.value, filename)
        return self.save_to_file(temporary_path, buffer_size)


class DeletedDocument(Document):
    objects = TrashCanManager()

    class Meta:
        proxy = True


@python_2_unicode_compatible
class DocumentVersion(models.Model):
    """
    Model that describes a document version and its properties
    """
    _pre_open_hooks = {}
    _post_save_hooks = {}

    @classmethod
    def register_pre_open_hook(cls, order, func):
        cls._pre_open_hooks[order] = func

    @classmethod
    def register_post_save_hook(cls, order, func):
        cls._post_save_hooks[order] = func

    document = models.ForeignKey(Document, verbose_name=_('Document'), related_name='versions')
    timestamp = models.DateTimeField(verbose_name=_('Timestamp'), auto_now_add=True)
    comment = models.TextField(blank=True, verbose_name=_('Comment'))

    # File related fields
    file = models.FileField(upload_to=UUID_FUNCTION, storage=storage_backend, verbose_name=_('File'))
    mimetype = models.CharField(max_length=255, null=True, blank=True, editable=False)
    encoding = models.CharField(max_length=64, null=True, blank=True, editable=False)

    checksum = models.TextField(blank=True, null=True, verbose_name=_('Checksum'), editable=False)

    class Meta:
        verbose_name = _('Document version')
        verbose_name_plural = _('Document version')

    def __str__(self):
        return '{0} - {1}'.format(self.document, self.timestamp)

    def save(self, *args, **kwargs):
        """
        Overloaded save method that updates the document version's checksum,
        mimetype, and page count when created
        """
        user = kwargs.pop('_user', None)

        new_document_version = not self.pk

        if new_document_version:
            logger.info('Creating new version for document: %s', self.document)

        try:
            with transaction.atomic():
                super(DocumentVersion, self).save(*args, **kwargs)

                for key in sorted(DocumentVersion._post_save_hooks):
                    DocumentVersion._post_save_hooks[key](self)

                if new_document_version:
                    # Only do this for new documents
                    self.update_checksum(save=False)
                    self.update_mimetype(save=False)
                    self.save()
                    self.update_page_count(save=False)

                    logger.info('New document "%s" version created for document: %s', self, self.document)

                    self.document.is_stub = False
                    self.document.save()
        except Exception as exception:
            logger.error('Error creating new document version for document "%s"; %s', self.document, exception)
            raise
        else:
            if new_document_version:
                event_document_new_version.commit(actor=user, target=self.document)
                post_version_upload.send(sender=self.__class__, instance=self)

                if tuple(self.document.versions.all()) == (self,):
                    post_document_created.send(sender=self.document.__class__, instance=self.document)

    def invalidate_cache(self):
        for page in self.pages.all():
            page.invalidate_cache()

    def update_checksum(self, save=True):
        """
        Open a document version's file and update the checksum field using the
        user provided checksum function
        """
        if self.exists():
            source = self.open()
            self.checksum = unicode(HASH_FUNCTION(source.read()))
            source.close()
            if save:
                self.save()

    def update_page_count(self, save=True):
        try:
            with self.open() as file_object:
                converter = converter_class(file_object=file_object, mime_type=self.mimetype)
                detected_pages = converter.get_page_count()
        except UnknownFileFormat:
            # If converter backend doesn't understand the format,
            # use 1 as the total page count
            detected_pages = 1

        with transaction.atomic():
            self.pages.all().delete()

            for page_number in range(detected_pages):
                DocumentPage.objects.create(
                    document_version=self, page_number=page_number + 1
                )

        # TODO: is this needed anymore
        if save:
            self.save()

        return detected_pages

    def revert(self, user=None):
        """
        Delete the subsequent versions after this one
        """
        logger.info('Reverting to document document: %s to version: %s', self.document, self)

        event_document_version_revert.commit(actor=user, target=self.document)

        for version in self.document.versions.filter(timestamp__gt=self.timestamp):
            version.delete()

    def update_mimetype(self, save=True):
        """
        Read a document verions's file and determine the mimetype by calling the
        get_mimetype wrapper
        """
        if self.exists():
            try:
                with self.open() as file_object:
                    self.mimetype, self.encoding = get_mimetype(file_object=file_object)
            except:
                self.mimetype = ''
                self.encoding = ''
            finally:
                if save:
                    self.save()

    def delete(self, *args, **kwargs):
        for page in self.pages.all():
            page.delete()

        self.file.storage.delete(self.file.path)

        return super(DocumentVersion, self).delete(*args, **kwargs)

    def exists(self):
        """
        Returns a boolean value that indicates if the document's file
        exists in storage
        """
        return self.file.storage.exists(self.file.path)

    def open(self, raw=False):
        """
        Return a file descriptor to a document version's file irrespective of
        the storage backend
        """
        if raw:
            return self.file.storage.open(self.file.path)
        else:
            result = self.file.storage.open(self.file.path)
            for key in sorted(DocumentVersion._pre_open_hooks):
                result = DocumentVersion._pre_open_hooks[key](result, self)

            return result

    def save_to_file(self, filepath, buffer_size=1024 * 1024):
        """
        Save a copy of the document from the document storage backend
        to the local filesystem
        """
        input_descriptor = self.open()
        output_descriptor = open(filepath, 'wb')
        while True:
            copy_buffer = input_descriptor.read(buffer_size)
            if copy_buffer:
                output_descriptor.write(copy_buffer)
            else:
                break

        output_descriptor.close()
        input_descriptor.close()
        return filepath

    @property
    def size(self):
        if self.exists():
            return self.file.storage.size(self.file.path)
        else:
            return None

    @property
    def page_count(self):
        return self.pages.count()

    @property
    def uuid(self):
        # Make cache UUID a mix of document UUID, version ID
        return '{}-{}'.format(self.document.uuid, self.pk)

    @property
    def cache_filename(self):
        return os.path.join(setting_cache_path.value, 'document-version-{}'.format(self.uuid))

    def get_intermidiate_file(self):
        cache_filename = self.cache_filename
        logger.debug('Intermidiate filename: %s', cache_filename)

        if os.path.exists(cache_filename):
            logger.debug('Intermidiate file "%s" found.', cache_filename)

            return open(cache_filename)
        else:
            logger.debug('Intermidiate file "%s" not found.', cache_filename)

            try:
                converter = converter_class(file_object=self.open())
                pdf_file_object = converter.to_pdf()

                with open(cache_filename, 'wb+') as file_object:
                    for chunk in pdf_file_object:
                        file_object.write(chunk)

                return open(cache_filename)
            except InvalidOfficeFormat:
                return self.open()
            except Exception as exception:
                # Cleanup in case of error
                logger.error('Error creating intermediate file "%s"; %s.', cache_filename, exception)
                fs_cleanup(cache_filename)
                raise


@python_2_unicode_compatible
class DocumentTypeFilename(models.Model):
    """
    List of filenames available to a specific document type for the
    quick rename functionality
    """
    document_type = models.ForeignKey(DocumentType, related_name='filenames', verbose_name=_('Document type'))
    filename = models.CharField(max_length=128, verbose_name=_('Filename'), db_index=True)
    enabled = models.BooleanField(default=True, verbose_name=_('Enabled'))

    def __str__(self):
        return self.filename

    class Meta:
        ordering = ('filename',)
        unique_together = ('document_type', 'filename')
        verbose_name = _('Document type quick rename filename')
        verbose_name_plural = _('Document types quick rename filenames')


@python_2_unicode_compatible
class DocumentPage(models.Model):
    """
    Model that describes a document version page
    """
    document_version = models.ForeignKey(DocumentVersion, verbose_name=_('Document version'), related_name='pages')
    page_number = models.PositiveIntegerField(default=1, editable=False, verbose_name=_('Page number'), db_index=True)

    def __str__(self):
        return _('Page %(page_num)d out of %(total_pages)d of %(document)s') % {
            'document': unicode(self.document),
            'page_num': self.page_number,
            'total_pages': self.document_version.pages.count()
        }

    class Meta:
        ordering = ('page_number',)
        verbose_name = _('Document page')
        verbose_name_plural = _('Document pages')

    def get_absolute_url(self):
        return reverse('documents:document_page_view', args=[self.pk])

    def delete(self, *args, **kwargs):
        self.invalidate_cache()
        super(DocumentPage, self).delete(*args, **kwargs)

    @property
    def siblings(self):
        return DocumentPage.objects.filter(document_version=self.document_version)

    # Compatibility methods
    @property
    def document(self):
        return self.document_version.document

    def invalidate_cache(self):
        fs_cleanup(self.cache_filename)

    @property
    def uuid(self):
        """
        Make cache UUID a mix of version ID and page ID to avoid using stale
        images
        """
        return '{}-{}'.format(self.document_version.uuid, self.pk)

    @property
    def cache_filename(self):
        return os.path.join(setting_cache_path.value, 'page-cache-{}'.format(self.uuid))

    def get_image(self, *args, **kwargs):
        as_base64 = kwargs.pop('as_base64', False)
        transformations = kwargs.pop('transformations', [])
        size = kwargs.pop('size', setting_display_size.value)
        rotation = kwargs.pop('rotation', DEFAULT_ROTATION)
        zoom_level = kwargs.pop('zoom', DEFAULT_ZOOM_LEVEL)

        if zoom_level < setting_zoom_min_level.value:
            zoom_level = setting_zoom_min_level.value

        if zoom_level > setting_zoom_max_level.value:
            zoom_level = setting_zoom_max_level.value

        rotation = rotation % 360

        cache_filename = self.cache_filename
        logger.debug('Page cache filename: %s', cache_filename)

        if os.path.exists(cache_filename):
            logger.debug('Page cache file "%s" found', cache_filename)
            converter = converter_class(file_object=open(cache_filename))

            converter.seek(0)
        else:
            logger.debug('Page cache file "%s" not found', cache_filename)

            try:
                converter = converter_class(file_object=self.document_version.get_intermidiate_file())
                converter.seek(page_number=self.page_number - 1)

                page_image = converter.get_page()
                with open(cache_filename, 'wb+') as file_object:
                    file_object.write(page_image.getvalue())
            except Exception as exception:
                # Cleanup in case of error
                logger.error('Error creating page cache file "%s"; %s', cache_filename, exception)
                fs_cleanup(cache_filename)
                raise

        # Stored transformations
        for stored_transformation in Transformation.objects.get_for_model(self, as_classes=True):
            converter.transform(transformation=stored_transformation)

        # Interactive transformations
        for transformation in transformations:
            converter.transform(transformation=transformation)

        if rotation:
            converter.transform(transformation=TransformationRotate(degrees=rotation))

        if size:
            converter.transform(transformation=TransformationResize(**dict(zip(('width', 'height'), (size.split('x'))))))

        if zoom_level:
            converter.transform(transformation=TransformationZoom(percent=zoom_level))

        page_image = converter.get_page()

        if as_base64:
            # TODO: don't prepend 'data:%s;base64,%s' part
            return 'data:%s;base64,%s' % ('image/png', base64.b64encode(page_image.getvalue()))
        else:
            return page_image


@python_2_unicode_compatible
class RecentDocument(models.Model):
    """
    Keeps a list of the n most recent accessed or created document for
    a given user
    """
    user = models.ForeignKey(User, verbose_name=_('User'), editable=False)
    document = models.ForeignKey(Document, verbose_name=_('Document'), editable=False)
    datetime_accessed = models.DateTimeField(verbose_name=_('Accessed'), auto_now=True, db_index=True)

    objects = RecentDocumentManager()

    def __str__(self):
        return unicode(self.document)

    class Meta:
        ordering = ('-datetime_accessed',)
        verbose_name = _('Recent document')
        verbose_name_plural = _('Recent documents')

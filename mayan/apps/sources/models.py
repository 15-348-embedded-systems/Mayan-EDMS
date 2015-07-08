from __future__ import unicode_literals

from email.Utils import collapse_rfc2231_value
from email import message_from_string
import json
import imaplib
import logging
import os
import poplib

from django.core.files import File
from django.db import models
from django.utils.encoding import python_2_unicode_compatible
from django.utils.translation import ugettext_lazy as _

from model_utils.managers import InheritanceManager

from common.compressed_files import CompressedFile, NotACompressedFile
from converter.literals import DIMENSION_SEPARATOR
from converter.models import Transformation
from djcelery.models import PeriodicTask, IntervalSchedule
from documents.models import Document, DocumentType
from documents.settings import setting_language
from metadata.api import save_metadata_list

from .classes import Attachment, SourceUploadedFile, StagingFile
from .literals import (
    DEFAULT_INTERVAL, DEFAULT_POP3_TIMEOUT, DEFAULT_IMAP_MAILBOX,
    SOURCE_CHOICES, SOURCE_CHOICE_STAGING, SOURCE_CHOICE_WATCH,
    SOURCE_CHOICE_WEB_FORM, SOURCE_INTERACTIVE_UNCOMPRESS_CHOICES,
    SOURCE_UNCOMPRESS_CHOICES, SOURCE_UNCOMPRESS_CHOICE_Y,
    SOURCE_CHOICE_EMAIL_IMAP, SOURCE_CHOICE_EMAIL_POP3
)

logger = logging.getLogger(__name__)


@python_2_unicode_compatible
class Source(models.Model):
    label = models.CharField(max_length=64, verbose_name=_('Label'))
    enabled = models.BooleanField(default=True, verbose_name=_('Enabled'))

    objects = InheritanceManager()

    @classmethod
    def class_fullname(cls):
        return unicode(dict(SOURCE_CHOICES).get(cls.source_type))

    def __str__(self):
        return '%s' % self.label

    def fullname(self):
        return ' '.join([self.class_fullname(), '"%s"' % self.label])

    def _upload_document(self, document_type, file_object, label, language, user, description=None, metadata_dict_list=None):
        document = document_type.new_document(
            file_object=file_object, label=label, description=description,
            language=language, _user=user
        )

        Transformation.objects.get_for_model(document).delete()
        Transformation.objects.copy(source=Source.objects.get_subclass(pk=self.pk), targets=Document.objects.filter(pk=document.pk))

        if metadata_dict_list:
            save_metadata_list(metadata_dict_list, document, create=True)

    # TODO: Rename this method to 'handle_upload' or similar
    def upload_document(self, file_object, label, description=None, document_type=None, expand=False, language=None, metadata_dict_list=None, user=None):
        if not document_type:
            document_type = self.document_type

        if expand:
            try:
                compressed_file = CompressedFile(file_object)
                for compressed_file_child in compressed_file.children():
                    self._upload_document(document_type=document_type, file_object=compressed_file_child, description=description, label=unicode(compressed_file_child), language=language or setting_language.value, metadata_dict_list=metadata_dict_list, user=user)
                    compressed_file_child.close()

            except NotACompressedFile:
                logging.debug('Exception: NotACompressedFile')
                self._upload_document(document_type=document_type, file_object=file_object, description=description, label=label, language=language or setting_language.value, metadata_dict_list=metadata_dict_list, user=user)
        else:
            self._upload_document(document_type=document_type, file_object=file_object, description=description, label=label, language=language or setting_language.value, metadata_dict_list=metadata_dict_list, user=user)

    def get_upload_file_object(self, form_data):
        pass
        # TODO: Should raise NotImplementedError()?

    def clean_up_upload_file(self, upload_file_object):
        pass
        # TODO: Should raise NotImplementedError()?

    class Meta:
        ordering = ('label',)
        verbose_name = _('Source')
        verbose_name_plural = _('Sources')


class InteractiveSource(Source):
    objects = InheritanceManager()

    class Meta:
        verbose_name = _('Interactive source')
        verbose_name_plural = _('Interactive sources')


class StagingFolderSource(InteractiveSource):
    is_interactive = True
    source_type = SOURCE_CHOICE_STAGING

    folder_path = models.CharField(max_length=255, verbose_name=_('Folder path'), help_text=_('Server side filesystem path.'))
    preview_width = models.IntegerField(verbose_name=_('Preview width'), help_text=_('Width value to be passed to the converter backend.'))
    preview_height = models.IntegerField(blank=True, null=True, verbose_name=_('Preview height'), help_text=_('Height value to be passed to the converter backend.'))
    uncompress = models.CharField(max_length=1, choices=SOURCE_INTERACTIVE_UNCOMPRESS_CHOICES, verbose_name=_('Uncompress'), help_text=_('Whether to expand or not compressed archives.'))
    delete_after_upload = models.BooleanField(default=True, verbose_name=_('Delete after upload'), help_text=_('Delete the file after is has been successfully uploaded.'))

    def get_preview_size(self):
        dimensions = []
        dimensions.append(unicode(self.preview_width))
        if self.preview_height:
            dimensions.append(unicode(self.preview_height))

        return DIMENSION_SEPARATOR.join(dimensions)

    def get_file(self, *args, **kwargs):
        return StagingFile(staging_folder=self, *args, **kwargs)

    def get_files(self):
        try:
            for entry in sorted([os.path.normcase(f) for f in os.listdir(self.folder_path) if os.path.isfile(os.path.join(self.folder_path, f))]):
                yield self.get_file(filename=entry)
        except OSError as exception:
            logger.error('Unable get list of staging files from source: %s; %s', self, exception)
            raise Exception(_('Unable get list of staging files: %s') % exception)

    def get_upload_file_object(self, form_data):
        staging_file = self.get_file(encoded_filename=form_data['staging_file_id'])
        return SourceUploadedFile(source=self, file=staging_file.as_file(), extra_data=staging_file)

    def clean_up_upload_file(self, upload_file_object):
        if self.delete_after_upload:
            try:
                upload_file_object.extra_data.delete()
            except Exception as exception:
                logger.error('Error deleting staging file: %s; %s', upload_file_object, exception)
                raise Exception(_('Error deleting staging file; %s') % exception)

    class Meta:
        verbose_name = _('Staging folder')
        verbose_name_plural = _('Staging folders')


class WebFormSource(InteractiveSource):
    is_interactive = True
    source_type = SOURCE_CHOICE_WEB_FORM

    # TODO: unify uncompress as an InteractiveSource field
    uncompress = models.CharField(max_length=1, choices=SOURCE_INTERACTIVE_UNCOMPRESS_CHOICES, verbose_name=_('Uncompress'), help_text=_('Whether to expand or not compressed archives.'))
    # Default path

    def get_upload_file_object(self, form_data):
        return SourceUploadedFile(source=self, file=form_data['file'])

    class Meta:
        verbose_name = _('Web form')
        verbose_name_plural = _('Web forms')


class OutOfProcessSource(Source):
    is_interactive = False

    class Meta:
        verbose_name = _('Out of process')
        verbose_name_plural = _('Out of process')


class IntervalBaseModel(OutOfProcessSource):
    interval = models.PositiveIntegerField(default=DEFAULT_INTERVAL, verbose_name=_('Interval'), help_text=_('Interval in seconds between checks for new documents.'))
    document_type = models.ForeignKey(DocumentType, verbose_name=_('Document type'), help_text=_('Assign a document type to documents uploaded from this source.'))
    uncompress = models.CharField(max_length=1, choices=SOURCE_UNCOMPRESS_CHOICES, verbose_name=_('Uncompress'), help_text=_('Whether to expand or not, compressed archives.'))

    def _get_periodic_task_name(self, pk=None):
        return 'check_interval_source-%i' % (pk or self.pk)

    def _delete_periodic_task(self, pk=None):
        periodic_task = PeriodicTask.objects.get(name=self._get_periodic_task_name(pk))

        interval_instance = periodic_task.interval

        if tuple(interval_instance.periodictask_set.values_list('id', flat=True)) == (periodic_task.pk,):
            # Only delete the interval if nobody else is using it
            interval_instance.delete()
        else:
            periodic_task.delete()

    def save(self, *args, **kwargs):
        new_source = not self.pk
        super(IntervalBaseModel, self).save(*args, **kwargs)

        if not new_source:
            self._delete_periodic_task()

        interval_instance, created = IntervalSchedule.objects.get_or_create(every=self.interval, period='seconds')
        # Create a new interval or reuse someone else's
        PeriodicTask.objects.create(
            name=self._get_periodic_task_name(),
            interval=interval_instance,
            task='sources.tasks.task_check_interval_source',
            queue='uploads',
            kwargs=json.dumps({'source_id': self.pk})
        )

    def delete(self, *args, **kwargs):
        pk = self.pk
        super(IntervalBaseModel, self).delete(*args, **kwargs)
        self._delete_periodic_task(pk)

    class Meta:
        verbose_name = _('Interval source')
        verbose_name_plural = _('Interval sources')


class EmailBaseModel(IntervalBaseModel):
    host = models.CharField(max_length=128, verbose_name=_('Host'))
    ssl = models.BooleanField(default=True, verbose_name=_('SSL'))
    port = models.PositiveIntegerField(blank=True, null=True, verbose_name=_('Port'), help_text=_('Typical choices are 110 for POP3, 995 for POP3 over SSL, 143 for IMAP, 993 for IMAP over SSL.'))
    username = models.CharField(max_length=96, verbose_name=_('Username'))
    password = models.CharField(max_length=96, verbose_name=_('Password'))

    # From: http://bookmarks.honewatson.com/2009/08/11/python-gmail-imaplib-search-subject-get-attachments/
    # TODO: Add lock to avoid running more than once concurrent same document download
    # TODO: Use message ID for lock
    @staticmethod
    def process_message(source, message):
        email = message_from_string(message)
        counter = 1

        for part in email.walk():
            disposition = part.get('Content-Disposition', 'none')
            logger.debug('Disposition: %s', disposition)

            if disposition.startswith('attachment'):
                raw_filename = part.get_filename()

                if raw_filename:
                    filename = collapse_rfc2231_value(raw_filename)
                else:
                    filename = _('attachment-%i') % counter
                    counter += 1

                logger.debug('filename: %s', filename)

                file_object = Attachment(part, name=filename)
                source.upload_document(file_object=file_object, label=filename, expand=(source.uncompress == SOURCE_UNCOMPRESS_CHOICE_Y), document_type=source.document_type)

    class Meta:
        verbose_name = _('Email source')
        verbose_name_plural = _('Email sources')


class POP3Email(EmailBaseModel):
    source_type = SOURCE_CHOICE_EMAIL_POP3

    timeout = models.PositiveIntegerField(default=DEFAULT_POP3_TIMEOUT, verbose_name=_('Timeout'))

    def check_source(self):
        logger.debug('Starting POP3 email fetch')
        logger.debug('host: %s', self.host)
        logger.debug('ssl: %s', self.ssl)

        if self.ssl:
            mailbox = poplib.POP3_SSL(self.host, self.port)
        else:
            mailbox = poplib.POP3(self.host, self.port, timeout=self.timeout)

        mailbox.getwelcome()
        mailbox.user(self.username)
        mailbox.pass_(self.password)
        messages_info = mailbox.list()

        logger.debug('messages_info:')
        logger.debug(messages_info)
        logger.debug('messages count: %s', len(messages_info[1]))

        for message_info in messages_info[1]:
            message_number, message_size = message_info.split()
            logger.debug('message_number: %s', message_number)
            logger.debug('message_size: %s', message_size)

            complete_message = '\n'.join(mailbox.retr(message_number)[1])

            EmailBaseModel.process_message(source=self, message=complete_message)
            mailbox.dele(message_number)

        mailbox.quit()

    class Meta:
        verbose_name = _('POP email')
        verbose_name_plural = _('POP email')


class IMAPEmail(EmailBaseModel):
    source_type = SOURCE_CHOICE_EMAIL_IMAP

    mailbox = models.CharField(max_length=64, default=DEFAULT_IMAP_MAILBOX, verbose_name=_('Mailbox'), help_text=_('Mail from which to check for messages with attached documents.'))

    # http://www.doughellmann.com/PyMOTW/imaplib/
    def check_source(self):
        logger.debug('Starting IMAP email fetch')
        logger.debug('host: %s', self.host)
        logger.debug('ssl: %s', self.ssl)

        if self.ssl:
            mailbox = imaplib.IMAP4_SSL(self.host, self.port)
        else:
            mailbox = imaplib.IMAP4(self.host, self.port)

        mailbox.login(self.username, self.password)
        mailbox.select(self.mailbox)

        status, data = mailbox.search(None, 'NOT', 'DELETED')
        if data:
            messages_info = data[0].split()
            logger.debug('messages count: %s', len(messages_info))

            for message_number in messages_info:
                logger.debug('message_number: %s', message_number)
                status, data = mailbox.fetch(message_number, '(RFC822)')
                EmailBaseModel.process_message(source=self, message=data[0][1])
                mailbox.store(message_number, '+FLAGS', '\\Deleted')

        mailbox.expunge()
        mailbox.close()
        mailbox.logout()

    class Meta:
        verbose_name = _('IMAP email')
        verbose_name_plural = _('IMAP email')


class WatchFolderSource(IntervalBaseModel):
    source_type = SOURCE_CHOICE_WATCH

    folder_path = models.CharField(max_length=255, verbose_name=_('Folder path'), help_text=_('Server side filesystem path.'))

    def check_source(self):
        for file_name in os.listdir(self.folder_path):
            full_path = os.path.join(self.folder_path, file_name)
            if os.path.isfile(full_path):

                with File(file=open(full_path, mode='rb')) as file_object:
                    self.upload_document(file_object, label=file_name, expand=(self.uncompress == SOURCE_UNCOMPRESS_CHOICE_Y))
                    os.unlink(full_path)

    class Meta:
        verbose_name = _('Watch folder')
        verbose_name_plural = _('Watch folders')


class SourceLog(models.Model):
    source = models.ForeignKey(Source, related_name='logs', verbose_name=_('Source'))
    datetime = models.DateTimeField(auto_now_add=True, editable=False, verbose_name=_('Date time'))
    message = models.TextField(blank=True, editable=False, verbose_name=_('Message'))

    class Meta:
        verbose_name = _('Log entry')
        verbose_name_plural = _('Log entries')
        get_latest_by = 'datetime'
        ordering = ('-datetime',)

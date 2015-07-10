from __future__ import unicode_literals

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.encoding import python_2_unicode_compatible
from django.utils.translation import ugettext_lazy as _

from documents.models import Document, DocumentType

from .managers import MetadataTypeManager
from .settings import setting_available_validators


def validation_choices():
    return zip(setting_available_validators.value, setting_available_validators.value)


@python_2_unicode_compatible
class MetadataType(models.Model):
    """
    Define a type of metadata
    """
    name = models.CharField(max_length=48, help_text=_('Do not use python reserved words, or spaces.'), unique=True, verbose_name=_('Name'))
    label = models.CharField(max_length=48, verbose_name=_('Label'))
    default = models.CharField(blank=True, max_length=128, null=True, help_text=_('Enter a string to be evaluated.'), verbose_name=_('Default'))
    # TODO: Add enable_lookup boolean to allow users to switch the lookup on and
    # off without losing the lookup expression
    lookup = models.TextField(blank=True, null=True, help_text=_('Enter a string to be evaluated that returns an iterable.'), verbose_name=_('Lookup'))
    validation = models.CharField(blank=True, choices=validation_choices(), max_length=64, verbose_name=_('Validation function name'))
    # TODO: Find a different way to let users know what models and functions are
    # available now that we removed these from the help_text
    objects = MetadataTypeManager()

    def __str__(self):
        return self.label

    def natural_key(self):
        return (self.name,)

    class Meta:
        ordering = ('label',)
        verbose_name = _('Metadata type')
        verbose_name_plural = _('Metadata types')


@python_2_unicode_compatible
class DocumentMetadata(models.Model):
    """
    Link a document to a specific instance of a metadata type with it's
    current value
    """
    document = models.ForeignKey(Document, related_name='metadata', verbose_name=_('Document'))
    metadata_type = models.ForeignKey(MetadataType, verbose_name=_('Type'))
    value = models.CharField(blank=True, db_index=True, max_length=255, null=True, verbose_name=_('Value'))

    def __str__(self):
        return unicode(self.metadata_type)

    def save(self, *args, **kwargs):
        if self.metadata_type.pk not in self.document.document_type.metadata.values_list('metadata_type', flat=True):
            raise ValidationError(_('Metadata type is not valid for this document type.'))

        return super(DocumentMetadata, self).save(*args, **kwargs)

    def delete(self, enforce_required=True, *args, **kwargs):
        if enforce_required and self.metadata_type.pk in self.document.document_type.metadata.filter(required=True).values_list('metadata_type', flat=True):
            raise ValidationError(_('Metadata type is required for this document type.'))

        return super(DocumentMetadata, self).delete(*args, **kwargs)

    class Meta:
        unique_together = ('document', 'metadata_type')
        verbose_name = _('Document metadata')
        verbose_name_plural = _('Document metadata')


@python_2_unicode_compatible
class DocumentTypeMetadataType(models.Model):
    document_type = models.ForeignKey(DocumentType, related_name='metadata', verbose_name=_('Document type'))
    metadata_type = models.ForeignKey(MetadataType, verbose_name=_('Metadata type'))
    required = models.BooleanField(default=False, verbose_name=_('Required'))

    def __str__(self):
        return unicode(self.metadata_type)

    class Meta:
        unique_together = ('document_type', 'metadata_type')
        verbose_name = _('Document type metadata type options')
        verbose_name_plural = _('Document type metadata types options')

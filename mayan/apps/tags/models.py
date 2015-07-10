from __future__ import unicode_literals

from django.db import models
from django.utils.encoding import python_2_unicode_compatible
from django.utils.translation import ugettext_lazy as _

from documents.models import Document

from .literals import COLOR_CHOICES, COLOR_CODES


@python_2_unicode_compatible
class Tag(models.Model):
    label = models.CharField(db_index=True, max_length=128, unique=True, verbose_name=_('Label'))
    color = models.CharField(choices=COLOR_CHOICES, max_length=3, verbose_name=_('Color'))
    documents = models.ManyToManyField(Document, related_name='tags', verbose_name=_('Documents'))

    class Meta:
        verbose_name = _('Tag')
        verbose_name_plural = _('Tags')

    def __str__(self):
        return self.label

    def get_color_code(self):
        return dict(COLOR_CODES)[self.color]

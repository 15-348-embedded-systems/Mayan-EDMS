from __future__ import unicode_literals

import logging

from django.db.models.signals import post_delete, post_save
from django.utils.translation import ugettext_lazy as _

from acls import ModelPermission
from common import (
    MayanAppConfig, menu_facet, menu_multi_item, menu_object, menu_secondary,
    menu_setup, menu_sidebar, menu_tools
)
from common.classes import ModelAttribute
from common.utils import encapsulate
from documents.models import Document, DocumentType
from documents.search import document_search
from documents.signals import post_document_type_change
from navigation import SourceColumn
from rest_api.classes import APIEndPoint

from .api import get_metadata_string
from .classes import DocumentMetadataHelper
from .handlers import (
    post_document_type_metadata_type_add,
    post_document_type_metadata_type_delete,
    post_post_document_type_change_metadata
)
from .links import (
    link_metadata_add, link_metadata_edit, link_metadata_multiple_add,
    link_metadata_multiple_edit, link_metadata_multiple_remove,
    link_metadata_remove, link_metadata_view, link_setup_document_type_metadata,
    link_setup_document_type_metadata_required, link_setup_metadata_type_create,
    link_setup_metadata_type_delete, link_setup_metadata_type_edit,
    link_setup_metadata_type_list, link_documents_missing_required_metadata
)
from .models import DocumentTypeMetadataType, MetadataType
from .permissions import (
    permission_metadata_document_add, permission_metadata_document_edit,
    permission_metadata_document_remove, permission_metadata_document_view
)

logger = logging.getLogger(__name__)


class MetadataApp(MayanAppConfig):
    name = 'metadata'
    verbose_name = _('Metadata')

    def ready(self):
        super(MetadataApp, self).ready()

        APIEndPoint('metadata')

        Document.add_to_class('metadata_value_of', DocumentMetadataHelper.constructor)

        ModelAttribute(Document, 'metadata', type_name='related', description=_('Queryset containing a MetadataType instance reference and a value for that metadata type'))
        ModelAttribute(Document, 'metadata__metadata_type__name', label=_('Metadata type name'), type_name='query')
        ModelAttribute(Document, 'metadata__value', label=_('Metadata type value'), type_name='query')
        ModelAttribute(Document, 'metadata_value_of', label=_('Value of a metadata'), description=_('Return the value of a specific document metadata'), type_name=['property', 'indexing'])

        ModelPermission.register(
            model=Document, permissions=(
                permission_metadata_document_add, permission_metadata_document_edit,
                permission_metadata_document_remove, permission_metadata_document_view,
            )
        )

        SourceColumn(source=Document, label=_('Metadata'), attribute=encapsulate(lambda document: get_metadata_string(document)))

        document_search.add_model_field(field='metadata__metadata_type__name', label=_('Metadata type'))
        document_search.add_model_field(field='metadata__value', label=_('Metadata value'))

        menu_facet.bind_links(links=[link_metadata_view], sources=[Document])
        menu_multi_item.bind_links(links=[link_metadata_multiple_add, link_metadata_multiple_edit, link_metadata_multiple_remove], sources=[Document])
        menu_object.bind_links(links=[link_setup_document_type_metadata, link_setup_document_type_metadata_required], sources=[DocumentType])
        menu_object.bind_links(links=[link_setup_metadata_type_edit, link_setup_metadata_type_delete], sources=[MetadataType])
        menu_secondary.bind_links(links=[link_setup_metadata_type_list, link_setup_metadata_type_create], sources=[MetadataType, 'metadata:setup_metadata_type_list', 'metadata:setup_metadata_type_create'])
        menu_setup.bind_links(links=[link_setup_metadata_type_list])
        menu_sidebar.bind_links(links=[link_metadata_add, link_metadata_edit, link_metadata_remove], sources=['metadata:metadata_add', 'metadata:metadata_edit', 'metadata:metadata_remove', 'metadata:metadata_view'])
        menu_tools.bind_links(links=[link_documents_missing_required_metadata])

        post_delete.connect(post_document_type_metadata_type_delete, dispatch_uid='post_document_type_metadata_type_delete', sender=DocumentTypeMetadataType)
        post_document_type_change.connect(post_post_document_type_change_metadata, dispatch_uid='post_post_document_type_change_metadata', sender=Document)
        post_save.connect(post_document_type_metadata_type_add, dispatch_uid='post_document_type_metadata_type_add', sender=DocumentTypeMetadataType)

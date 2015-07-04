from __future__ import absolute_import, unicode_literals

from django.utils.translation import ugettext_lazy as _

from actstream import registry

from acls import ModelPermission
from acls.links import link_acl_list
from acls.permissions import permission_acl_edit, permission_acl_view
from common import (
    MayanAppConfig, MissingItem, menu_facet, menu_front_page, menu_object,
    menu_secondary, menu_setup, menu_sidebar, menu_multi_item, menu_tools
)
from common.classes import ModelAttribute
from common.signals import post_initial_setup
from common.utils import encapsulate
from converter.links import link_transformation_list
from converter.permissions import (
    permission_transformation_create,
    permission_transformation_delete, permission_transformation_edit,
    permission_transformation_view,
)
from events.permissions import permission_events_view
from navigation import SourceColumn
from rest_api.classes import APIEndPoint
from statistics.classes import StatisticNamespace

from .handlers import create_default_document_type
from .links import (
    link_clear_image_cache, link_document_clear_transformations,
    link_document_delete, link_document_document_type_edit,
    link_document_events_view, link_document_multiple_document_type_edit,
    link_document_download, link_document_edit, link_document_list,
    link_document_list_deleted, link_document_list_recent,
    link_document_multiple_delete, link_document_multiple_trash,
    link_document_multiple_clear_transformations,
    link_document_multiple_download, link_document_multiple_restore,
    link_document_multiple_update_page_count,
    link_document_page_navigation_first, link_document_page_navigation_last,
    link_document_page_navigation_next, link_document_page_navigation_previous,
    link_document_page_return, link_document_page_rotate_left,
    link_document_page_rotate_right, link_document_page_view,
    link_document_page_view_reset, link_document_page_zoom_in,
    link_document_page_zoom_out, link_document_pages, link_document_preview,
    link_document_print, link_document_properties, link_document_restore,
    link_document_trash, link_document_type_create, link_document_type_delete,
    link_document_type_edit, link_document_type_filename_create,
    link_document_type_filename_delete, link_document_type_filename_edit,
    link_document_type_filename_list, link_document_type_list,
    link_document_type_setup, link_document_update_page_count,
    link_document_version_download, link_document_version_list,
    link_document_version_revert, link_trash_can_empty
)
from .models import (
    DeletedDocument, Document, DocumentPage, DocumentType, DocumentTypeFilename,
    DocumentVersion
)
from .permissions import (
    permission_document_delete, permission_document_download,
    permission_document_edit, permission_document_new_version,
    permission_document_print, permission_document_properties_edit,
    permission_document_trash, permission_document_version_revert,
    permission_document_view
)
from .settings import setting_thumbnail_size
from .statistics import DocumentStatistics, DocumentUsageStatistics
from .widgets import document_thumbnail


class DocumentsApp(MayanAppConfig):
    name = 'documents'
    verbose_name = _('Documents')

    def ready(self):
        super(DocumentsApp, self).ready()

        APIEndPoint('documents')

        MissingItem(label=_('Create a document type'), description=_('Every uploaded document must be assigned a document type, it is the basic way Mayan EDMS categorizes documents.'), condition=lambda: not DocumentType.objects.exists(), view='documents:document_type_list')

        ModelAttribute(Document, label=_('Label'), name='label', type_name='field')

        ModelPermission.register(
            model=Document, permissions=(
                permission_acl_edit, permission_acl_view,
                permission_document_delete, permission_document_download,
                permission_document_edit, permission_document_new_version,
                permission_document_print, permission_document_properties_edit,
                permission_document_trash, permission_document_version_revert,
                permission_document_view, permission_events_view,
                permission_transformation_create,
                permission_transformation_delete,
                permission_transformation_edit, permission_transformation_view,
            )
        )

        SourceColumn(source=Document, label=_('Thumbnail'), attribute=encapsulate(lambda document: document_thumbnail(document, gallery_name='documents:document_list', title=getattr(document, 'label', None), size=setting_thumbnail_size.value)))
        SourceColumn(source=Document, label=_('Type'), attribute='document_type')
        SourceColumn(source=DeletedDocument, label=_('Type'), attribute='document_type')
        SourceColumn(source=DeletedDocument, label=_('Date time deleted'), attribute='deleted_date_time')

        menu_front_page.bind_links(links=[link_document_list_recent, link_document_list, link_document_list_deleted])
        menu_setup.bind_links(links=[link_document_type_setup])
        menu_tools.bind_links(links=[link_clear_image_cache])

        # Document type links
        menu_object.bind_links(links=[link_document_type_edit, link_document_type_filename_list, link_document_type_delete], sources=[DocumentType])
        menu_object.bind_links(links=[link_document_type_filename_edit, link_document_type_filename_delete], sources=[DocumentTypeFilename])
        menu_secondary.bind_links(links=[link_document_type_list, link_document_type_create], sources=[DocumentType, 'documents:document_type_create', 'documents:document_type_list'])
        menu_sidebar.bind_links(links=[link_document_type_filename_create], sources=[DocumentTypeFilename, 'documents:document_type_filename_list', 'documents:document_type_filename_create'])

        menu_sidebar.bind_links(links=[link_trash_can_empty], sources=['documents:document_list_deleted', 'documents:trash_can_empty'])

        # Document object links
        menu_object.bind_links(links=[link_document_edit, link_document_document_type_edit, link_document_print, link_document_trash, link_document_download, link_document_clear_transformations, link_document_update_page_count], sources=[Document])
        menu_object.bind_links(links=[link_document_restore, link_document_delete], sources=[DeletedDocument])

        # Document facet links
        menu_facet.bind_links(links=[link_acl_list], sources=[Document])
        menu_facet.bind_links(links=[link_document_preview], sources=[Document], position=0)
        menu_facet.bind_links(links=[link_document_properties], sources=[Document], position=2)
        menu_facet.bind_links(links=[link_document_events_view, link_document_version_list], sources=[Document], position=2)
        menu_facet.bind_links(links=[link_document_pages], sources=[Document])

        # Document actions
        menu_object.bind_links(links=[link_document_version_revert, link_document_version_download], sources=[DocumentVersion])
        menu_multi_item.bind_links(links=[link_document_multiple_clear_transformations, link_document_multiple_trash, link_document_multiple_download, link_document_multiple_update_page_count, link_document_multiple_document_type_edit], sources=[Document])
        menu_multi_item.bind_links(links=[link_document_multiple_restore, link_document_multiple_delete], sources=[DeletedDocument])

        # Document pages
        menu_facet.bind_links(links=[link_document_page_rotate_left, link_document_page_rotate_right, link_document_page_zoom_in, link_document_page_zoom_out, link_document_page_view_reset], sources=['documents:document_page_view'])
        menu_facet.bind_links(links=[link_document_page_return, link_document_page_view], sources=[DocumentPage])
        menu_facet.bind_links(links=[link_document_page_navigation_first, link_document_page_navigation_previous, link_document_page_navigation_next, link_document_page_navigation_last, link_transformation_list], sources=[DocumentPage])
        menu_object.bind_links(links=[link_transformation_list], sources=[DocumentPage])

        namespace = StatisticNamespace(name='documents', label=_('Documents'))
        namespace.add_statistic(DocumentStatistics(name='document_stats', label=_('Document tendencies')))
        namespace.add_statistic(DocumentUsageStatistics(name='document_usage', label=_('Document usage')))

        post_initial_setup.connect(create_default_document_type, dispatch_uid='create_default_document_type')

        registry.register(Document)

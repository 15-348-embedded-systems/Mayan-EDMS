from __future__ import absolute_import, unicode_literals

from django.utils.translation import ugettext_lazy as _

from common import (
    MayanAppConfig, MissingItem, menu_front_page, menu_object, menu_secondary,
    menu_sidebar, menu_setup
)
from common.signals import post_initial_setup
from common.utils import encapsulate
from converter.links import link_transformation_list
from documents.models import Document
from documents.signals import post_version_upload
from navigation import SourceColumn
from rest_api.classes import APIEndPoint

from .classes import StagingFile
from .handlers import (
    copy_transformations_to_version, create_default_document_source
)
from .links import (
    link_document_create_multiple, link_document_create_siblings,
    link_setup_sources, link_setup_source_create_imap_email,
    link_setup_source_create_pop3_email,
    link_setup_source_create_watch_folder, link_setup_source_create_webform,
    link_setup_source_create_staging_folder, link_setup_source_delete,
    link_setup_source_edit, link_setup_source_logs, link_staging_file_delete,
    link_upload_version
)
from .models import Source
from .widgets import staging_file_thumbnail


class SourcesApp(MayanAppConfig):
    name = 'sources'
    verbose_name = _('Sources')

    def ready(self):
        super(SourcesApp, self).ready()

        APIEndPoint('sources')

        MissingItem(label=_('Create a document source'), description=_('Document sources are the way in which new documents are feed to Mayan EDMS, create at least a web form source to be able to upload documents from a browser.'), condition=lambda: not Source.objects.exists(), view='sources:setup_source_list')

        SourceColumn(source=StagingFile, label=_('Thumbnail'), attribute=encapsulate(lambda staging_file: staging_file_thumbnail(staging_file, gallery_name='sources:staging_list', title=staging_file.filename, size='100')))

        menu_front_page.bind_links(links=[link_document_create_multiple])
        menu_object.bind_links(links=[link_document_create_siblings], sources=[Document])
        menu_object.bind_links(links=[link_setup_source_edit, link_setup_source_delete, link_transformation_list, link_setup_source_logs], sources=[Source])
        menu_object.bind_links(links=[link_staging_file_delete], sources=[StagingFile])
        menu_secondary.bind_links(links=[link_setup_sources, link_setup_source_create_webform, link_setup_source_create_staging_folder, link_setup_source_create_pop3_email, link_setup_source_create_imap_email, link_setup_source_create_watch_folder], sources=[Source, 'sources:setup_source_list', 'sources:setup_source_create'])
        menu_setup.bind_links(links=[link_setup_sources])
        menu_sidebar.bind_links(links=[link_upload_version], sources=['documents:document_version_list', 'documents:upload_version', 'documents:document_version_revert'])

        post_initial_setup.connect(create_default_document_source, dispatch_uid='create_default_document_source')
        post_version_upload.connect(copy_transformations_to_version, dispatch_uid='copy_transformations_to_version')

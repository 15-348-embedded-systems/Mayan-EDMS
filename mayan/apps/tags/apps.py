from __future__ import unicode_literals

from django.utils.translation import ugettext_lazy as _

from acls.api import class_permissions
from acls.links import link_acl_list
from acls.permissions import permission_acl_edit, permission_acl_view
from common import (
    MayanAppConfig, menu_facet, menu_secondary, menu_object, menu_main,
    menu_multi_item, menu_sidebar
)
from common.utils import encapsulate
from documents.models import Document
from documents.search import document_search
from navigation import CombinedSource, SourceColumn
from rest_api.classes import APIEndPoint

from .links import (
    link_multiple_documents_attach_tag, link_multiple_documents_tag_remove,
    link_single_document_multiple_tag_remove, link_tag_attach, link_tag_create,
    link_tag_delete, link_tag_document_list, link_tag_edit, link_tag_list,
    link_tag_multiple_delete, link_tag_tagged_item_list
)
from .models import Tag
from .permissions import (
    permission_tag_attach, permission_tag_delete, permission_tag_edit,
    permission_tag_remove, permission_tag_view
)
from .widgets import widget_inline_tags, widget_single_tag


class TagsApp(MayanAppConfig):
    name = 'tags'
    verbose_name = _('Tags')

    def ready(self):
        super(TagsApp, self).ready()

        APIEndPoint('tags')

        SourceColumn(source=Document, label=_('Tags'), attribute=encapsulate(lambda document: widget_inline_tags(document)))

        SourceColumn(source=Tag, label=_('Preview'), attribute=encapsulate(lambda tag: widget_single_tag(tag)))
        SourceColumn(source=Tag, label=_('Tagged items'), attribute=encapsulate(lambda tag: tag.documents.count()))

        class_permissions(Document, [
            permission_tag_attach, permission_tag_remove,
        ])
        class_permissions(Tag, [
            permission_acl_edit, permission_acl_view, permission_tag_delete,
            permission_tag_edit, permission_tag_view,
        ])

        document_search.add_model_field(field='tags__label', label=_('Tags'))

        menu_facet.bind_links(links=[link_tag_document_list], sources=[Document])
        menu_main.bind_links(links=[link_tag_list])
        menu_multi_item.bind_links(links=[link_multiple_documents_attach_tag, link_multiple_documents_tag_remove], sources=[Document])
        menu_multi_item.bind_links(links=[link_tag_multiple_delete], sources=[Tag])
        menu_multi_item.bind_links(links=[link_single_document_multiple_tag_remove], sources=[CombinedSource(obj=Tag, view='tags:document_tags')])
        menu_object.bind_links(links=[link_tag_tagged_item_list, link_tag_edit, link_acl_list, link_tag_delete], sources=[Tag])
        menu_secondary.bind_links(links=[link_tag_list, link_tag_create], sources=[Tag, 'tags:tag_list', 'tags:tag_create'])
        menu_sidebar.bind_links(links=[link_tag_attach], sources=['tags:document_tags', 'tags:tag_remove', 'tags:tag_multiple_remove', 'tags:tag_attach'])

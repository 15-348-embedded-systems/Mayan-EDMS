from __future__ import unicode_literals

from django.conf.urls import patterns, url

from .api_views import (
    APIDocumentView, APIDocumentImageView, APIDocumentListView,
    APIDocumentPageView, APIDocumentTypeDocumentListView,
    APIDocumentTypeListView, APIDocumentTypeView,
    APIDocumentVersionCreateView, APIDocumentVersionView,
    APIRecentDocumentListView
)
from .settings import setting_print_size, setting_display_size
from .views import (
    DeletedDocumentListView, DocumentListView, DocumentManyRestoreView,
    DocumentPageListView, DocumentRestoreView, RecentDocumentListView
)

urlpatterns = patterns(
    'documents.views',
    url(r'^list/$', DocumentListView.as_view(), name='document_list'),
    url(r'^list/recent/$', RecentDocumentListView.as_view(), name='document_list_recent'),
    url(r'^list/deleted/$', DeletedDocumentListView.as_view(), name='document_list_deleted'),

    url(r'^(?P<document_id>\d+)/preview/$', 'document_preview', name='document_preview'),
    url(r'^(?P<document_id>\d+)/properties/$', 'document_properties', name='document_properties'),
    url(r'^(?P<pk>\d+)/restore/$', DocumentRestoreView.as_view(), name='document_restore'),
    url(r'^multiple/restore/$', DocumentManyRestoreView.as_view(), name='document_multiple_restore'),
    url(r'^(?P<document_id>\d+)/type/$', 'document_document_type_edit', name='document_document_type_edit'),
    url(r'^multiple/type/$', 'document_multiple_document_type_edit', name='document_multiple_document_type_edit'),
    url(r'^(?P<document_id>\d+)/delete/$', 'document_delete', name='document_delete'),
    url(r'^multiple/delete/$', 'document_multiple_delete', name='document_multiple_delete'),
    url(r'^(?P<document_id>\d+)/edit/$', 'document_edit', name='document_edit'),
    url(r'^(?P<document_id>\d+)/print/$', 'document_print', name='document_print'),
    url(r'^(?P<document_id>\d+)/reset_page_count/$', 'document_update_page_count', name='document_update_page_count'),
    url(r'^multiple/reset_page_count/$', 'document_multiple_update_page_count', name='document_multiple_update_page_count'),

    url(r'^(?P<document_id>\d+)/display/$', 'get_document_image', {'size': setting_display_size.value}, 'document_display'),
    url(r'^(?P<document_id>\d+)/display/print/$', 'get_document_image', {'size': setting_print_size.value}, 'document_display_print'),

    url(r'^(?P<document_id>\d+)/download/$', 'document_download', name='document_download'),
    url(r'^multiple/download/$', 'document_multiple_download', name='document_multiple_download'),
    url(r'^(?P<document_id>\d+)/clear_transformations/$', 'document_clear_transformations', name='document_clear_transformations'),

    url(r'^(?P<document_pk>\d+)/version/all/$', 'document_version_list', name='document_version_list'),
    url(r'^document/version/(?P<document_version_pk>\d+)/download/$', 'document_download', name='document_version_download'),
    url(r'^document/version/(?P<document_version_pk>\d+)/revert/$', 'document_version_revert', name='document_version_revert'),

    url(r'^(?P<pk>\d+)/pages/all/$', DocumentPageListView.as_view(), name='document_pages'),

    url(r'^multiple/clear_transformations/$', 'document_multiple_clear_transformations', name='document_multiple_clear_transformations'),
    url(r'^maintenance/clear_image_cache/$', 'document_clear_image_cache', name='document_clear_image_cache'),

    url(r'^page/(?P<document_page_id>\d+)/$', 'document_page_view', name='document_page_view'),
    url(r'^page/(?P<document_page_id>\d+)/navigation/next/$', 'document_page_navigation_next', name='document_page_navigation_next'),
    url(r'^page/(?P<document_page_id>\d+)/navigation/previous/$', 'document_page_navigation_previous', name='document_page_navigation_previous'),
    url(r'^page/(?P<document_page_id>\d+)/navigation/first/$', 'document_page_navigation_first', name='document_page_navigation_first'),
    url(r'^page/(?P<document_page_id>\d+)/navigation/last/$', 'document_page_navigation_last', name='document_page_navigation_last'),
    url(r'^page/(?P<document_page_id>\d+)/zoom/in/$', 'document_page_zoom_in', name='document_page_zoom_in'),
    url(r'^page/(?P<document_page_id>\d+)/zoom/out/$', 'document_page_zoom_out', name='document_page_zoom_out'),
    url(r'^page/(?P<document_page_id>\d+)/rotate/right/$', 'document_page_rotate_right', name='document_page_rotate_right'),
    url(r'^page/(?P<document_page_id>\d+)/rotate/left/$', 'document_page_rotate_left', name='document_page_rotate_left'),
    url(r'^page/(?P<document_page_id>\d+)/reset/$', 'document_page_view_reset', name='document_page_view_reset'),

    # Admin views
    url(r'^type/list/$', 'document_type_list', name='document_type_list'),
    url(r'^type/create/$', 'document_type_create', name='document_type_create'),
    url(r'^type/(?P<document_type_id>\d+)/edit/$', 'document_type_edit', name='document_type_edit'),
    url(r'^type/(?P<document_type_id>\d+)/delete/$', 'document_type_delete', name='document_type_delete'),

    url(r'^type/(?P<document_type_id>\d+)/filename/list/$', 'document_type_filename_list', name='document_type_filename_list'),
    url(r'^type/filename/(?P<document_type_filename_id>\d+)/edit/$', 'document_type_filename_edit', name='document_type_filename_edit'),
    url(r'^type/filename/(?P<document_type_filename_id>\d+)/delete/$', 'document_type_filename_delete', name='document_type_filename_delete'),
    url(r'^type/(?P<document_type_id>\d+)/filename/create/$', 'document_type_filename_create', name='document_type_filename_create'),
)

api_urls = patterns(
    '',
    url(r'^documents/$', APIDocumentListView.as_view(), name='document-list'),
    url(r'^documents/recent/$', APIRecentDocumentListView.as_view(), name='document-recent-list'),
    url(r'^documents/(?P<pk>[0-9]+)/$', APIDocumentView.as_view(), name='document-detail'),
    url(r'^document_version/(?P<pk>[0-9]+)/$', APIDocumentVersionView.as_view(), name='documentversion-detail'),
    url(r'^document_page/(?P<pk>[0-9]+)/$', APIDocumentPageView.as_view(), name='documentpage-detail'),
    url(r'^documents/(?P<pk>[0-9]+)/image/$', APIDocumentImageView.as_view(), name='document-image'),
    url(r'^documents/(?P<pk>[0-9]+)/new_version/$', APIDocumentVersionCreateView.as_view(), name='document-new-version'),
    url(r'^documenttypes/(?P<pk>[0-9]+)/documents/$', APIDocumentTypeDocumentListView.as_view(), name='documenttype-document-list'),
    url(r'^documenttypes/(?P<pk>[0-9]+)/$', APIDocumentTypeView.as_view(), name='documenttype-detail'),
    url(r'^documenttypes/$', APIDocumentTypeListView.as_view(), name='documenttype-list'),
)

from __future__ import unicode_literals

from django.conf.urls import patterns, url

from .views import SetupSmartLinkDocumentTypesView

urlpatterns = patterns(
    'linking.views',
    url(r'^document/(?P<document_id>\d+)/$', 'smart_link_instances_for_document', name='smart_link_instances_for_document'),
    url(r'^document/(?P<document_id>\d+)/smart_link/(?P<smart_link_pk>\d+)/$', 'smart_link_instance_view', name='smart_link_instance_view'),

    url(r'^setup/list/$', 'smart_link_list', name='smart_link_list'),
    url(r'^setup/create/$', 'smart_link_create', name='smart_link_create'),
    url(r'^setup/(?P<smart_link_pk>\d+)/delete/$', 'smart_link_delete', name='smart_link_delete'),
    url(r'^setup/(?P<smart_link_pk>\d+)/edit/$', 'smart_link_edit', name='smart_link_edit'),
    url(r'^setup/(?P<pk>\d+)/document_types/$', SetupSmartLinkDocumentTypesView.as_view(), name='smart_link_document_types'),

    url(r'^setup/(?P<smart_link_pk>\d+)/condition/list/$', 'smart_link_condition_list', name='smart_link_condition_list'),
    url(r'^setup/(?P<smart_link_pk>\d+)/condition/create/$', 'smart_link_condition_create', name='smart_link_condition_create'),
    url(r'^setup/smart_link/condition/(?P<smart_link_condition_pk>\d+)/edit/$', 'smart_link_condition_edit', name='smart_link_condition_edit'),
    url(r'^setup/smart_link/condition/(?P<smart_link_condition_pk>\d+)/delete/$', 'smart_link_condition_delete', name='smart_link_condition_delete'),
)

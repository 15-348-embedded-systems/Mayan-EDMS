from __future__ import unicode_literals

from django.utils.translation import ugettext_lazy as _

from navigation import Link


def is_superuser(context):
    return context['request'].user.is_staff or context['request'].user.is_superuser


link_about = Link(icon='fa fa-question', text=_('About'), view='common:about_view')
link_current_user_details = Link(icon='fa fa-user', text=_('User details'), view='common:current_user_details')
link_current_user_edit = Link(icon='fa fa-user', text=_('Edit details'), view='common:current_user_edit')
link_current_user_locale_profile_details = Link(icon='fa fa-globe', text=_('Locale profile'), view='common:current_user_locale_profile_details')
link_current_user_locale_profile_edit = Link(icon='fa fa-globe', text=_('Edit locale profile'), view='common:current_user_locale_profile_edit')
link_license = Link(icon='fa fa-book', text=_('License'), view='common:license_view')
link_maintenance_menu = Link(icon='fa fa-wrench', text=_('Maintenance'), view='common:maintenance_menu')
link_setup = Link(icon='fa fa-gear', text=_('Setup'), view='common:setup_list')
link_tools = Link(icon='fa fa-wrench', text=_('Tools'), view='common:tools_list')

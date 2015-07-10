from __future__ import unicode_literals

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied
from django.core.files import File
from django.core.urlresolvers import reverse
from django.test.client import Client
from django.test import TestCase

from .classes import Permission
from .models import Role, StoredPermission
from .permissions import permission_role_view


class PermissionTestCase(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create(username='test user')
        self.group = Group.objects.create(name='test group')
        self.role = Role.objects.create(label='test role')
        Permission.invalidate_cache()

    def test_no_permissions(self):
        with self.assertRaises(PermissionDenied):
            Permission.check_permissions(requester=self.user, permissions=(permission_role_view,))

    def test_with_permissions(self):
        self.group.user_set.add(self.user)
        self.role.permissions.add(permission_role_view.stored_permission)
        self.role.groups.add(self.group)

        try:
            Permission.check_permissions(requester=self.user, permissions=(permission_role_view,))
        except PermissionDenied:
            self.fail('PermissionDenied exception was not expected.')

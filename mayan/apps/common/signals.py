from __future__ import unicode_literals

from django.dispatch import Signal

post_initial_setup = Signal(use_caching=True)

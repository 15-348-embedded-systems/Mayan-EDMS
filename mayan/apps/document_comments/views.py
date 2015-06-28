from __future__ import absolute_import, unicode_literals

from django.conf import settings
from django.contrib import messages
from django.contrib.comments.models import Comment
from django.contrib.contenttypes.models import ContentType
from django.contrib.sites.models import Site
from django.core.exceptions import PermissionDenied
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect
from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext
from django.utils.translation import ugettext_lazy as _

from acls.models import AccessEntry
from documents.models import Document
from permissions.models import Permission

from .forms import CommentForm
from .permissions import (
    permission_comment_create, permission_comment_delete,
    permission_comment_view
)


def comment_delete(request, comment_id=None, comment_id_list=None):
    post_action_redirect = None

    if comment_id:
        comments = [get_object_or_404(Comment, pk=comment_id)]
    elif comment_id_list:
        comments = [get_object_or_404(Comment, pk=comment_id) for comment_id in comment_id_list.split(',')]

    try:
        Permission.objects.check_permissions(request.user, [permission_comment_delete])
    except PermissionDenied:
        comments = AccessEntry.objects.filter_objects_by_access(permission_comment_delete, request.user, comments, related='content_object')

    if not comments:
        messages.error(request, _('Must provide at least one comment.'))
        return HttpResponseRedirect(request.META.get('HTTP_REFERER', reverse(settings.LOGIN_REDIRECT_URL)))

    previous = request.POST.get('previous', request.GET.get('previous', request.META.get('HTTP_REFERER', reverse(settings.LOGIN_REDIRECT_URL))))
    next = request.POST.get('next', request.GET.get('next', post_action_redirect if post_action_redirect else request.META.get('HTTP_REFERER', reverse(settings.LOGIN_REDIRECT_URL))))

    if request.method == 'POST':
        for comment in comments:
            try:
                comment.delete()
                messages.success(request, _('Comment "%s" deleted successfully.') % comment)
            except Exception as exception:
                messages.error(request, _('Error deleting comment "%(comment)s": %(error)s') % {
                    'comment': comment, 'error': exception
                })

        return HttpResponseRedirect(next)

    context = {
        'delete_view': True,
        'previous': previous,
        'next': next,
    }
    if len(comments) == 1:
        context['object'] = comments[0].content_object
        context['title'] = _('Are you sure you wish to delete the comment: %s?') % ', '.join([unicode(d) for d in comments])
    elif len(comments) > 1:
        context['title'] = _('Are you sure you wish to delete the comments: %s?') % ', '.join([unicode(d) for d in comments])

    return render_to_response('appearance/generic_confirm.html', context,
                              context_instance=RequestContext(request))


def comment_multiple_delete(request):
    return comment_delete(
        request, comment_id_list=request.GET.get('id_list', [])
    )


def comment_add(request, document_id):
    document = get_object_or_404(Document, pk=document_id)

    try:
        Permission.objects.check_permissions(request.user, [permission_comment_create])
    except PermissionDenied:
        AccessEntry.objects.check_access(permission_comment_create, request.user, document)

    post_action_redirect = None

    next = request.POST.get('next', request.GET.get('next', post_action_redirect if post_action_redirect else request.META.get('HTTP_REFERER', reverse(settings.LOGIN_REDIRECT_URL))))

    if request.method == 'POST':
        form = CommentForm(request.POST)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.user = request.user
            comment.content_type = ContentType.objects.get_for_model(document)
            comment.object_pk = document.pk
            comment.site = Site.objects.get_current()
            comment.save()

            messages.success(request, _('Comment added successfully.'))
            return HttpResponseRedirect(next)
    else:
        form = CommentForm()

    return render_to_response('appearance/generic_form.html', {
        'form': form,
        'title': _('Add comment to document: %s') % document,
        'next': next,
        'object': document,
    }, context_instance=RequestContext(request))


def comments_for_document(request, document_id):
    """
    Show a list of all the comments related to the passed object
    """
    document = get_object_or_404(Document, pk=document_id)

    try:
        Permission.objects.check_permissions(request.user, [permission_comment_view])
    except PermissionDenied:
        AccessEntry.objects.check_access(permission_comment_view, request.user, document)

    return render_to_response('appearance/generic_list.html', {
        'object': document,
        'access_object': document,
        'title': _('Comments for document: %s') % document,
        'object_list': Comment.objects.for_model(document).order_by('-submit_date'),
        'hide_link': True,
        'hide_object': True,
    }, context_instance=RequestContext(request))

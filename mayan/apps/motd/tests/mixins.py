from ..models import Message

from .literals import (
    TEST_LABEL, TEST_LABEL_EDITED, TEST_MESSAGE, TEST_MESSAGE_EDITED
)


class MOTDAPITestMixin:
    def _request_message_create_view(self):
        return self.post(
            viewname='rest_api:message-list', data={
                'label': TEST_LABEL, 'message': TEST_MESSAGE
            }
        )

    def _request_message_delete_view(self):
        return self.delete(
            viewname='rest_api:message-detail', kwargs={
                'pk': self.test_message.pk
            }
        )

    def _request_message_detail_view(self):
        return self.get(
            viewname='rest_api:message-detail', kwargs={
                'pk': self.test_message.pk
            }
        )

    def _request_message_edit_via_patch_view(self):
        return self.patch(
            viewname='rest_api:message-detail', kwargs={
                'pk': self.test_message.pk
            }, data={
                'label': TEST_LABEL_EDITED,
                'message': TEST_MESSAGE_EDITED
            }
        )

    def _request_message_edit_via_put_view(self):
        return self.put(
            viewname='rest_api:message-detail', kwargs={
                'pk': self.test_message.pk
            }, data={
                'label': TEST_LABEL_EDITED,
                'message': TEST_MESSAGE_EDITED
            }
        )


class MOTDTestMixin:
    def _create_test_message(self):
        self.test_message = Message.objects.create(
            label=TEST_LABEL, message=TEST_MESSAGE
        )

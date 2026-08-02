from src.channels.base import Channel
from src.channels.log import LogChannel
from src.delivery.coordinator import NotificationDelivery
from src.delivery.idempotent_channel import DurableIdempotentChannel
from src.delivery.sqlite import NotificationDeliveryStore
from src.notifications.model import MergeRequestNotification, PipelineNotification


def test_notification_contracts_are_available_from_responsibility_modules():
    assert Channel.__module__ == "src.channels.base"
    assert LogChannel.__module__ == "src.channels.log"
    assert MergeRequestNotification.__module__ == "src.notifications.model"
    assert PipelineNotification.__module__ == "src.notifications.model"


def test_delivery_components_are_available_from_responsibility_modules():
    assert NotificationDeliveryStore.__module__ == "src.delivery.sqlite"
    assert DurableIdempotentChannel.__module__ == "src.delivery.idempotent_channel"
    assert NotificationDelivery.__module__ == "src.delivery.coordinator"

from src.delivery.coordinator import NotificationDelivery
from src.delivery.idempotent_channel import DurableIdempotentChannel
from src.delivery.sqlite import NotificationDeliveryStore


def test_delivery_components_are_available_from_responsibility_modules():
    assert NotificationDeliveryStore.__module__ == "src.delivery.sqlite"
    assert DurableIdempotentChannel.__module__ == "src.delivery.idempotent_channel"
    assert NotificationDelivery.__module__ == "src.delivery.coordinator"

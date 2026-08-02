def test_gidgetlab_runtime_import_is_available():
    from gitlab_bot import GitLabBot

    assert GitLabBot is not None


def test_merge_notification_recovery_is_registered_on_startup():
    from gitlab_bot import bot, recover_merge_notification_deliveries

    assert recover_merge_notification_deliveries in bot.app.on_startup

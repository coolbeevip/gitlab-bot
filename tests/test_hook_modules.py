from src.hooks.approval_notification import ApprovalNotificationHooks, build_notification
from src.hooks.merge_notification import MergeRequestNotificationHooks, build_merged_notification
from src.hooks.pipeline_notification import PipelineNotificationHooks, build_pipeline_notification


def test_notification_hooks_are_available_from_responsibility_modules():
    assert ApprovalNotificationHooks.__module__ == "src.hooks.approval_notification"
    assert MergeRequestNotificationHooks.__module__ == "src.hooks.merge_notification"
    assert PipelineNotificationHooks.__module__ == "src.hooks.pipeline_notification"
    assert build_notification.__module__ == "src.hooks.approval_notification"
    assert build_merged_notification.__module__ == "src.hooks.merge_notification"
    assert build_pipeline_notification.__module__ == "src.hooks.pipeline_notification"

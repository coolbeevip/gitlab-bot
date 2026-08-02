"""Representative GitLab Pipeline Hook payloads."""

from copy import deepcopy


def make_pipeline_webhook(*, status="success", include_merge_request=True, username="pipeline-trigger"):
    payload = {
        "object_kind": "pipeline",
        "user": {
            "id": 7,
            "name": "Pipeline Trigger",
            "username": username,
        },
        "project": {
            "id": 76,
            "name": "Project",
            "path_with_namespace": "group/project",
            "web_url": "https://gitlab.example.com/group/project",
        },
        "object_attributes": {
            "id": 31,
            "iid": 3,
            "name": "Pipeline for branch: master",
            "ref": "master",
            "tag": False,
            "sha": "bcbb5ec396a2c0f828686f14fac9b80b780504f2",
            "source": "push",
            "status": status,
            "detailed_status": "passed" if status == "success" else "failed",
            "created_at": "2026-08-02T10:05:00Z",
            "finished_at": "2026-08-02T10:06:03Z",
            "duration": 63,
            "queued_duration": 10,
            "url": "https://gitlab.example.com/group/project/-/pipelines/31",
        },
        "commit": {
            "id": "bcbb5ec396a2c0f828686f14fac9b80b780504f2",
            "message": "Merge branch feature",
        },
    }
    if include_merge_request:
        payload["merge_request"] = {
            "id": 1,
            "iid": 12,
            "title": "Add feature",
            "source_branch": "feature",
            "target_branch": "master",
            "url": "https://gitlab.example.com/group/project/-/merge_requests/12",
        }
    return payload


PIPELINE_WEBHOOK = make_pipeline_webhook()
FAILED_PIPELINE_WEBHOOK = make_pipeline_webhook(status="failed")


def copy_pipeline_webhook(**kwargs):
    if not kwargs:
        return deepcopy(PIPELINE_WEBHOOK)
    return make_pipeline_webhook(**kwargs)

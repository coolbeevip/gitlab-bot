from copy import deepcopy

APPROVALS_EMPTY_GET = {
    "approved": False,
    "approvals_required": None,
    "approvals_left": None,
    "approved_by": [],
}

APPROVALS_ROBOT_GET = {
    "approved": True,
    "approvals_required": None,
    "approvals_left": None,
    "approved_by": [
        {
            "user": {
                "id": 28,
                "username": "review-bot",
                "name": "review-bot",
            }
        }
    ],
}

APPROVALS_OTHER_USER_GET = {
    "approved": True,
    "approvals_required": None,
    "approvals_left": None,
    "approved_by": [
        {
            "user": {
                "id": 29,
                "username": "other-reviewer",
                "name": "Other Reviewer",
            }
        }
    ],
}

APPROVE_RESPONSE = {
    "user_has_approved": True,
    "user_can_approve": False,
    "approved": True,
    "approved_by": [
        {
            "user": {
                "id": 28,
                "username": "review-bot",
                "name": "review-bot",
            }
        }
    ],
}

UNAPPROVE_RESPONSE = {
    "user_has_approved": False,
    "user_can_approve": True,
    "approved": False,
    "approved_by": [],
}


class ApprovalApiFake:
    """Async fake for the subset of gidgetlab used by approval tests."""

    def __init__(self, responses):
        self._responses = {key: list(values) for key, values in responses.items()}
        self.calls = []

    async def getitem(self, url):
        return self._respond("GET", url, None)

    async def post(self, url, data=None):
        return self._respond("POST", url, data)

    def _respond(self, method, url, data):
        self.calls.append((method, url, data))
        key = (method, url)
        if key not in self._responses or not self._responses[key]:
            raise AssertionError(f"No fake response configured for {method} {url}")
        return deepcopy(self._responses[key].pop(0))

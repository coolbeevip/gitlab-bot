def test_gidgetlab_runtime_import_is_available():
    from gitlab_bot import GitLabBot

    assert GitLabBot is not None

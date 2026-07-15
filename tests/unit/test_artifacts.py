from wilson_eval3ngine.evidence.store import LocalArtifactStore


def test_content_addressed_artifact_store(tmp_path):
    store = LocalArtifactStore(tmp_path)
    first = store.put_bytes("project-a", b"evidence", media_type="text/plain")
    second = store.put_bytes("project-a", b"evidence", media_type="text/plain")
    assert first.sha256 == second.sha256
    assert store.verify(first)
    assert store.get_bytes(first) == b"evidence"


def test_artifact_project_path_rejects_traversal(tmp_path):
    store = LocalArtifactStore(tmp_path)
    try:
        store.put_bytes("../escape", b"x", media_type="text/plain")
    except ValueError as exc:
        assert "project_id" in str(exc)
    else:
        raise AssertionError("path traversal was not rejected")

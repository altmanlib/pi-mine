from app.options import resolve_user_path


def test_resolve_user_path_expands_home(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    target = tmp_path / "pi-sessions"
    target.mkdir()
    resolved = resolve_user_path("~/pi-sessions")
    assert resolved == target.resolve()


def test_resolve_user_path_absolute(tmp_path) -> None:
    resolved = resolve_user_path(tmp_path)
    assert resolved == tmp_path.resolve()
    assert resolved.is_absolute()

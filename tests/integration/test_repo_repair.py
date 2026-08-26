"""Repair end-to-end test: config_bak_* archived, user configs restored verbatim, switch succeeds."""
import shutil
import subprocess
import tempfile
from pathlib import Path

import pygit2

from utilities.repo_repair import detect_broken_state, repair_broken_worktree


def git(cwd: Path, *args):
    subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, check=True)


def make_origin(tmp: Path) -> Path:
    work = tmp / "work"
    origin = tmp / "origin.git"
    work.mkdir()
    origin.mkdir()
    subprocess.run(["git", "init", "--bare", str(origin)], check=True, capture_output=True)
    subprocess.run(["git", "init", str(work)], check=True, capture_output=True)
    git(work, "config", "user.email", "t@t.com")
    git(work, "config", "user.name", "t")
    git(work, "remote", "add", "origin", str(origin))
    (work / "config").mkdir(parents=True)
    (work / "config" / "templates").mkdir(parents=True)
    (work / "config" / "templates" / "a.yaml.template").write_text("a: tmpl\n")
    (work / ".gitignore").write_text("config/*.yaml\n")
    git(work, "add", ".")
    git(work, "commit", "-m", "main")
    git(work, "branch", "-M", "main")
    git(work, "push", "-u", "origin", "main")
    git(work, "checkout", "-b", "dev")
    (work / "tracked.txt").write_text("dev\n")
    git(work, "add", ".")
    git(work, "commit", "-m", "dev")
    git(work, "push", "-u", "origin", "dev")
    git(work, "checkout", "-b", "dev_test")
    (work / "tracked.txt").write_text("dev_test\n")
    git(work, "add", ".")
    git(work, "commit", "-m", "dev_test")
    git(work, "push", "-u", "origin", "dev_test")
    return origin


def test_repair_archives_config_bak_and_restores(tmp_path: Path):
    tmp = Path(tempfile.mkdtemp(dir=str(tmp_path)))
    try:
        origin = make_origin(tmp)
        aio = tmp_path / "aio"
        aio.mkdir()
        target = aio / "xbridge_trading_bots"
        from utilities.git_repo_management import GitRepoManagement
        mgr = GitRepoManagement(str(origin), str(target), branch="dev", workdir=str(aio))
        mgr.portable_python_dir = None
        mgr.portable_python_path = None
        mgr.git_repo.clone_or_update()
        # Simulate broken state: create config_bak with user config
        bak = target / "config_bak_20260826_145328"
        bak.mkdir()
        (bak / "config_pingpong.yaml").write_text("user: value\n")
        (bak / "api_keys.local.json").write_text('{"k":"v"}')
        # Also modify tracked file that differs in dev_test to exercise blocker backup
        (target / "tracked.txt").write_text("local mod\n")
        # Switch to dev_test (should auto-backup tracked.txt)
        mgr2 = GitRepoManagement(str(origin), str(target), branch="dev_test", workdir=str(aio))
        mgr2.portable_python_dir = None
        mgr2.portable_python_path = None
        mgr2.git_repo.clone_or_update()
        # Now repair archives baks and restores configs
        info = detect_broken_state(target)
        assert info["broken"] is True
        report = repair_broken_worktree(target, aio_folder=aio, branch="dev_test")
        assert "config_pingpong.yaml" in str(report["restored_configs"])
        assert (target / "config" / "config_pingpong.yaml").read_text() == "user: value\n"
        assert (target / "config" / "api_keys.local.json").read_text() == '{"k":"v"}'
        # Bak dir should be gone from worktree, archived in backup
        assert not bak.exists()
        assert len(report["orphans_archived"]) == 1
        # data/logs should remain (ignored) - not part of test but check no crash
        repo = pygit2.Repository(str(target))
        assert repo.head.shorthand == "dev_test"
    finally:
        shutil.rmtree(str(tmp), ignore_errors=True)


def test_detect_not_broken_when_clean(tmp_path: Path):
    aio = tmp_path / "aio"
    aio.mkdir()
    target = aio / "xbridge_trading_bots"
    target.mkdir()
    (target / ".git").mkdir()
    info = detect_broken_state(target)
    assert info["broken"] is False

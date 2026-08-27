"""Integration tests for clean branch migration (real pygit2 repos in /tmp).

All tests use tmp_path only - never touch ~/.AIO_Blocknet.
"""

import shutil
import tempfile
from pathlib import Path

import pygit2
import pytest


def _init_bare_origin(path: Path) -> pygit2.Repository:
    repo = pygit2.init_repository(str(path), bare=True)
    return repo


def _commit(repo: pygit2.Repository, message: str, files: dict, branch: str = "main") -> pygit2.Oid:
    """Create a commit on branch with given files dict {rel_path: content}."""
    # Write files to workdir (repo is not bare for commits; we use a temp worktree)
    # Instead use low-level: create blobs and tree
    # For simplicity, use a temporary worktree clone via pygit2
    raise NotImplementedError


# Helpers using subprocess git for brevity (requires git binary, but tests that need git are fine;
# the app itself does NOT require git - this is test helper only).

import subprocess


def git(cwd: Path, *args):
    result = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, check=True)
    return result.stdout.strip()


def make_origin_with_branches(tmp: Path):
    """Create bare origin with main, dev, dev_test branches for tests.

    main: templates/config_a.yaml.template + tracked.txt="main"
    dev: adds config_a change + same templates
    dev_test: modifies tracked.txt and adds new_file.txt
    """
    work = tmp / "work"
    origin = tmp / "origin.git"
    work.mkdir()
    origin.mkdir()
    git(tmp, "init", "--bare", "origin.git")
    git(work, "init")
    git(work, "config", "user.email", "test@test.com")
    git(work, "config", "user.name", "test")
    git(work, "remote", "add", "origin", str(origin))

    # main
    (work / "tracked.txt").write_text("main\n")
    (work / "config").mkdir()
    (work / "config" / "templates").mkdir(parents=True)
    (work / "config" / "templates" / "a.yaml.template").write_text("a: 1\n")
    (work / "data").mkdir()
    (work / "data" / ".gitkeep").write_text("")
    (work / ".gitignore").write_text("config/*.yaml\nconfig/*.json\ndata/*\n!data/.gitkeep\nlogs/\nvenv/\n")
    git(work, "add", ".")
    git(work, "commit", "-m", "main")
    git(work, "branch", "-M", "main")
    git(work, "push", "-u", "origin", "main")

    # dev
    git(work, "checkout", "-b", "dev")
    (work / "tracked.txt").write_text("dev\n")
    git(work, "add", "tracked.txt")
    git(work, "commit", "-m", "dev")
    git(work, "push", "-u", "origin", "dev")

    # dev_test from dev
    git(work, "checkout", "-b", "dev_test")
    (work / "tracked.txt").write_text("dev_test\n")
    (work / "new_file.txt").write_text("new in dev_test\n")
    git(work, "add", ".")
    git(work, "commit", "-m", "dev_test")
    git(work, "push", "-u", "origin", "dev_test")

    return origin


@pytest.fixture
def origin_repo(tmp_path: Path):
    tmp = Path(tempfile.mkdtemp(dir=str(tmp_path)))
    origin = make_origin_with_branches(tmp)
    yield origin
    shutil.rmtree(str(tmp), ignore_errors=True)


def _clone_via_manager(origin: Path, target: Path, branch: str = "main", workdir: Path = None):
    from utilities.git_repo_management import GitRepoManagement

    mgr = GitRepoManagement(str(origin), str(target), branch=branch, workdir=str(workdir) if workdir else None)
    # Disable portable python install path for tests (no network)
    mgr.portable_python_dir = None
    mgr.portable_python_path = None
    # Patch venv creation to no-op (avoid python -m venv requiring real python)
    mgr.git_repo.clone_or_update()
    return mgr


def test_clean_switch_dev_to_dev_test(tmp_path: Path, origin_repo: Path):
    from utilities.git_repo_management import GitRepoManagement

    aio = tmp_path / "aio"
    aio.mkdir()
    target = aio / "xbridge_trading_bots"
    mgr = GitRepoManagement(str(origin_repo), str(target), branch="dev", workdir=str(aio))
    mgr.portable_python_dir = None
    mgr.portable_python_path = None
    mgr.git_repo.clone_or_update()
    repo = pygit2.Repository(str(target))
    assert repo.head.shorthand == "dev"
    assert not repo.head_is_detached
    # Switch to dev_test
    mgr2 = GitRepoManagement(str(origin_repo), str(target), branch="dev_test", workdir=str(aio))
    mgr2.portable_python_dir = None
    mgr2.portable_python_path = None
    mgr2.git_repo.clone_or_update()
    repo = pygit2.Repository(str(target))
    assert repo.head.shorthand == "dev_test"
    assert not repo.head_is_detached
    assert (target / "new_file.txt").read_text() == "new in dev_test\n"
    assert (target / "tracked.txt").read_text() == "dev_test\n"


def test_modified_tracked_blocker_auto_backup(tmp_path: Path, origin_repo: Path):
    aio = tmp_path / "aio"
    aio.mkdir()
    target = aio / "xbridge_trading_bots"
    from utilities.git_repo_management import GitRepoManagement

    mgr = GitRepoManagement(str(origin_repo), str(target), branch="dev", workdir=str(aio))
    mgr.portable_python_dir = None
    mgr.portable_python_path = None
    mgr.git_repo.clone_or_update()
    # Modify tracked file that differs in dev_test
    (target / "tracked.txt").write_text("locally modified\n")
    mgr2 = GitRepoManagement(str(origin_repo), str(target), branch="dev_test", workdir=str(aio))
    mgr2.portable_python_dir = None
    mgr2.portable_python_path = None
    mgr2.git_repo.clone_or_update()
    repo = pygit2.Repository(str(target))
    assert repo.head.shorthand == "dev_test"
    assert not repo.head_is_detached
    assert (target / "tracked.txt").read_text() == "dev_test\n"
    # Backup exists
    backups = list((aio / "backups").glob("*_checkout"))
    assert len(backups) >= 1
    # Find backup containing tracked.txt
    found = any((b / "tracked.txt").exists() for b in backups)
    assert found


def test_venv_outside_worktree_not_blocker(tmp_path: Path, origin_repo: Path):
    aio = tmp_path / "aio"
    aio.mkdir()
    target = aio / "xbridge_trading_bots"
    from utilities.git_repo_management import GitRepoManagement

    mgr = GitRepoManagement(str(origin_repo), str(target), branch="dev", workdir=str(aio))
    mgr.portable_python_dir = None
    mgr.portable_python_path = None
    mgr.git_repo.clone_or_update()
    # Relocated venv outside worktree should not appear in status / not block
    venv_outside = aio / "xbridge_trading_bots_venv"
    venv_outside.mkdir()
    (venv_outside / "dummy.txt").write_text("venv content")
    mgr2 = GitRepoManagement(str(origin_repo), str(target), branch="dev_test", workdir=str(aio))
    mgr2.portable_python_dir = None
    mgr2.portable_python_path = None
    # Should switch cleanly
    mgr2.git_repo.clone_or_update()
    repo = pygit2.Repository(str(target))
    assert repo.head.shorthand == "dev_test"


def test_bidirectional_switch(tmp_path: Path, origin_repo: Path):
    aio = tmp_path / "aio"
    aio.mkdir()
    target = aio / "xbridge_trading_bots"
    from utilities.git_repo_management import GitRepoManagement

    for branch in ["dev", "dev_test", "dev", "dev_test"]:
        mgr = GitRepoManagement(str(origin_repo), str(target), branch=branch, workdir=str(aio))
        mgr.portable_python_dir = None
        mgr.portable_python_path = None
        mgr.git_repo.clone_or_update()
        repo = pygit2.Repository(str(target))
        assert repo.head.shorthand == branch
        assert not repo.head_is_detached

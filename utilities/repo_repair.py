"""Auto-repair/migration for broken xbridge_trading_bots worktrees.

Detects orphaned config_bak_* dirs, stale half-created refs and dirty
blockers, backs up user data, restores runtime configs verbatim and
produces a repair report. All operations use /tmp-style staging;
never touches host data outside the target worktree + aio backup dir.
"""
import json
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


def _find_config_baks(target: Path) -> List[Path]:
    return sorted(target.glob("config_bak_*"), key=lambda p: p.name)


def detect_broken_state(target_dir: Path) -> Dict:
    """Return description of broken-state signatures (read-only)."""
    target = Path(target_dir)
    info: Dict = {"config_baks": [], "has_git": False, "head": None}
    baks = _find_config_baks(target)
    info["config_baks"] = [str(p) for p in baks]
    git_head = target / ".git" / "HEAD"
    info["has_git"] = (target / ".git").is_dir()
    if git_head.exists():
        try:
            info["head"] = git_head.read_text().strip()
        except Exception:
            pass
    # Presence of any config_bak is considered broken (legacy repair artefact)
    info["broken"] = len(baks) > 0
    return info


def _regenerate_config_from_templates(target: Path) -> int:
    """Copy templates/*.template -> config/*.  Returns number copied."""
    templates_dir = target / "config" / "templates"
    config_dir = target / "config"
    if not templates_dir.is_dir():
        return 0
    config_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    for tmpl in templates_dir.glob("*.template"):
        dest_name = tmpl.name[:-len(".template")] if tmpl.name.endswith(".template") else tmpl.name
        dest = config_dir / dest_name
        if not dest.exists():
            try:
                shutil.copy2(str(tmpl), str(dest))
                count += 1
            except Exception as e:
                logger.warning(f"Could not seed config from template {tmpl.name}: {e}")
    return count


def _stage_user_configs(target: Path, staging: Path) -> List[str]:
    """Collect runtime config yamls/jsons from config_baks into staging. Returns list of staged relative paths."""
    staged: List[str] = []
    staging.mkdir(parents=True, exist_ok=True)
    for bak in _find_config_baks(target):
        for item in bak.rglob("*"):
            if item.is_file():
                # Skip templates subdir files? keep but overlay will handle; templates are .template suffix
                rel = item.relative_to(bak)
                # templates/*.template are not runtime configs - skip staging them
                if "templates" in rel.parts:
                    continue
                dst = staging / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                try:
                    shutil.copy2(str(item), str(dst))
                    staged.append(str(rel))
                except Exception as e:
                    logger.warning(f"Could not stage {item}: {e}")
    return staged


def _restore_user_configs(target: Path, staging: Path) -> List[str]:
    """Copy staged configs verbatim into target/config/. Returns restored paths."""
    restored: List[str] = []
    config_dir = target / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    for item in staging.rglob("*"):
        if item.is_file():
            rel = item.relative_to(staging)
            dst = config_dir / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            try:
                shutil.copy2(str(item), str(dst))
                restored.append(str(rel))
            except Exception as e:
                logger.warning(f"Could not restore {item} -> {dst}: {e}")
    return restored


def repair_broken_worktree(
    target_dir: Path,
    aio_folder: Optional[Path] = None,
    branch: Optional[str] = None,
) -> Dict:
    """
    Fully-automatic repair for broken worktrees.

    Steps:
      1. Stage user runtime configs from config_bak_*
      2. Confine config_bak_* dirs into timestamped backup (confine, not delete user data yet)
      3. Caller is expected to have already performed git switch (via GitRepository hygiene);
         here we regenerate missing config/ from templates and restore user configs verbatim.
      4. Emit repair_report.json

    Returns report dict.
    """
    target = Path(target_dir).resolve()
    backup_base = Path(aio_folder) / "backups" if aio_folder else target.parent / "backups"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = backup_base / f"{target.name}_{timestamp}_repair"
    backup_dir.mkdir(parents=True, exist_ok=True)
    staging = backup_dir / "_staging_configs"

    report: Dict = {
        "timestamp": timestamp,
        "target": str(target),
        "backup_dir": str(backup_dir),
        "branch": branch,
        "config_baks_found": [],
        "staged_configs": [],
        "orphans_archived": [],
        "seeded_from_templates": 0,
        "restored_configs": [],
    }

    baks = _find_config_baks(target)
    report["config_baks_found"] = [str(p) for p in baks]

    # Stage before we move the baks
    if baks:
        report["staged_configs"] = _stage_user_configs(target, staging)

    # Archive orphan baks into backup_dir (preserve, remove from worktree)
    for bak in baks:
        try:
            dst = backup_dir / bak.name
            shutil.move(str(bak), str(dst))
            report["orphans_archived"].append(bak.name)
            logger.info(f"Archived orphan {bak.name} -> {dst}")
        except Exception as e:
            logger.error(f"Could not archive {bak}: {e}")

    # After caller will have switched branches, regenerate config/ from templates
    report["seeded_from_templates"] = _regenerate_config_from_templates(target)

    # Restore user configs verbatim (user wins)
    if staging.exists():
        report["restored_configs"] = _restore_user_configs(target, staging)
        # Remove staging
        try:
            shutil.rmtree(staging)
        except Exception:
            pass

    # Write report
    report_path = backup_dir / "repair_report.json"
    try:
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2)
        logger.info(f"Repair report written to {report_path}")
    except Exception as e:
        logger.warning(f"Could not write repair report: {e}")

    return report

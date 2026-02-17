"""
Sync options schema: single source of truth for CLI.

All configurable options with env keys, defaults, types, and CLI flags.
Used to build argparse and set env overrides.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, List, Optional

if TYPE_CHECKING:
    import argparse

# -----------------------------------------------------------------------------
# Option definition: (env_key, default, type, cli_flag, help_text, choices?)
# -----------------------------------------------------------------------------

@dataclass
class SyncOption:
    """One configurable option."""
    key: str                          # internal key (e.g. "owner_name")
    env_key: Optional[str]            # env var (e.g. PLAYLIST_OWNER_NAME); None = runtime-only
    default: Any
    kind: str                         # "bool", "int", "str", "path", "choice"
    cli_flag: Optional[str]           # e.g. --owner-name; None = no CLI
    cli_negatable: bool = False       # for bool: add --no-* variant
    help_text: str = ""
    choices: Optional[List[Any]] = None
    label: str = ""
    section: str = "sync"             # sync | playlist | naming | reports | advanced


def _opts() -> List[SyncOption]:
    return [
        # ----- Runtime (no env; control flow only) -----
        SyncOption("skip_sync", None, False, "bool", "--skip-sync", False,
                   "Skip library sync; use existing data only.", section="sync",
                   label="Skip library sync"),
        SyncOption("sync_only", None, False, "bool", "--sync-only", False,
                   "Only sync library; do not update playlists.", section="sync",
                   label="Sync only (no playlists)"),
        SyncOption("force", None, False, "bool", "--force", False,
                   "Force full sync without cache.", section="sync",
                   label="Force full refresh"),
        SyncOption("verbose", None, False, "bool", "--verbose", False,
                   "Enable verbose logging.", section="sync",
                   label="Verbose logging"),
        SyncOption("all_months", None, False, "bool", "--all-months", False,
                   "Process all months (not just last N).", section="sync",
                   label="Process all months"),
        SyncOption("steps", None, None, "str", "--steps", False,
                   "Comma-separated steps to run (default: all). Steps: sync, rename, delete_monthly_and_genre, consolidate, update_current_year, descriptions, health_check, insights_report.",
                   section="sync", label="Steps to run"),
        # ----- Data -----
        SyncOption("data_dir", "SPOTIM8_DATA_DIR", None, "path", "--data-dir", False,
                   "Data directory (parquet files). Overrides default.", section="sync",
                   label="Data folder path"),
        # ----- Playlist naming (most used) -----
        SyncOption("owner_name", "PLAYLIST_OWNER_NAME", "AJ", "str", "--owner-name", False,
                   "Owner name used in playlist titles.", section="naming",
                   label="Owner name"),
        SyncOption("base_prefix", "PLAYLIST_PREFIX", "Finds", "str", "--prefix", False,
                   "Prefix for Finds (yearly) playlists.", section="naming",
                   label="Finds playlist prefix"),
        SyncOption("keep_monthly_months", "KEEP_MONTHLY_MONTHS", 3, "int", "--keep-monthly-months", False,
                   "Legacy: months to keep (v6 uses yearly only).", section="playlist",
                   label="Keep last N months"),
        # ----- Playlist type toggles -----
        SyncOption("enable_monthly", "PLAYLIST_ENABLE_MONTHLY", True, "bool", "--enable-monthly", True,
                   "Enable Finds (liked-songs) yearly playlists.", section="playlist",
                   label="Finds playlists"),
        SyncOption("enable_most_played", "PLAYLIST_ENABLE_MOST_PLAYED", True, "bool", "--enable-most-played", True,
                   "Enable most-played playlists.", section="playlist",
                   label="Most played playlists"),
        SyncOption("enable_discovery", "PLAYLIST_ENABLE_DISCOVERY", True, "bool", "--enable-discovery", True,
                   "Enable discovery playlists.", section="playlist",
                   label="Discovery playlists"),
        # ----- Prefixes (advanced naming) -----
        SyncOption("prefix_monthly", "PLAYLIST_PREFIX_MONTHLY", None, "str", "--prefix-monthly", False,
                   "Prefix for Finds yearly (default: same as --prefix).", section="naming",
                   label="Finds prefix override"),
        SyncOption("prefix_yearly", "PLAYLIST_PREFIX_YEARLY", None, "str", "--prefix-yearly", False,
                   "Prefix for yearly playlists.", section="naming",
                   label="Yearly prefix"),
        SyncOption("prefix_most_played", "PLAYLIST_PREFIX_MOST_PLAYED", "Top", "str", "--prefix-most-played", False,
                   "Prefix for most-played playlists.", section="naming",
                   label="Most played prefix"),
        SyncOption("prefix_discovery", "PLAYLIST_PREFIX_DISCOVERY", "Discovery", "str", "--prefix-discovery", False,
                   "Prefix for discovery playlists.", section="naming",
                   label="Discovery prefix"),
        # ----- Post-sync reports -----
        SyncOption("enable_health_check", "ENABLE_HEALTH_CHECK", False, "bool", "--enable-health-check", True,
                   "Run health check after sync.", section="reports",
                   label="Health check after sync"),
        SyncOption("enable_insights_report", "ENABLE_INSIGHTS_REPORT", False, "bool", "--enable-insights-report", True,
                   "Generate insights report after sync.", section="reports",
                   label="Insights report after sync"),
        # ----- Descriptions (v6: no mood/genre) -----
        SyncOption("enable_mood_tags", "ENABLE_MOOD_TAGS", False, "bool", "--enable-mood-tags", True,
                   "Legacy: mood tags (v6 descriptions are base-line only).", section="advanced",
                   label="Mood tags"),
        SyncOption("mood_max_tags", "MOOD_MAX_TAGS", 5, "int", "--mood-max-tags", False,
                   "Legacy: max mood tags.", section="advanced",
                   label="Max mood tags"),
        # ----- Formatting -----
        SyncOption("date_format", "PLAYLIST_DATE_FORMAT", "short", "choice", "--date-format", False,
                   "Date format: short, medium, long, numeric.", section="advanced",
                   label="Date format", choices=["short", "medium", "long", "numeric"]),
        SyncOption("capitalization", "PLAYLIST_CAPITALIZATION", "preserve", "choice", "--capitalization", False,
                   "Playlist name capitalization.", section="advanced",
                   label="Capitalization", choices=["title", "upper", "lower", "preserve"]),
        # ----- Library sync behavior -----
        SyncOption("owned_only", "SYNC_OWNED_ONLY", True, "bool", "--owned-only", True,
                   "Sync only playlists you own.", section="sync",
                   label="Only my playlists"),
        SyncOption("include_liked_songs", "SYNC_INCLUDE_LIKED_SONGS", True, "bool", "--include-liked-songs", True,
                   "Include Liked Songs in sync.", section="sync",
                   label="Include Liked Songs"),
    ]


SYNC_OPTIONS: List[SyncOption] = _opts()

# Ordered list of sync step IDs (for --steps). Must match step dispatch in sync.py.
SYNC_STEP_IDS: List[str] = [
    "sync",
    "rename",
    "delete_monthly_and_genre",
    "consolidate",
    "update_current_year",
    "descriptions",
    "health_check",
    "insights_report",
]


def parse_steps(steps_str: Optional[str]) -> Optional[List[str]]:
    """Parse --steps 'a,b,c' into list of step ids in SYNC_STEP_IDS order. Invalid ids skipped. None/empty -> None (run all)."""
    if not steps_str or not str(steps_str).strip():
        return None
    requested = [s.strip().lower() for s in str(steps_str).split(",") if s.strip()]
    valid = [s for s in SYNC_STEP_IDS if s in requested]
    # If user passed --steps but all invalid, return [] (run nothing). Else return valid or None.
    return valid if valid else [] if requested else None


def requested_unknown_steps(steps_str: Optional[str]) -> List[str]:
    """Return list of requested step ids that are not in SYNC_STEP_IDS (for warnings)."""
    if not steps_str or not str(steps_str).strip():
        return []
    requested = [s.strip().lower() for s in str(steps_str).split(",") if s.strip()]
    return [s for s in requested if s not in SYNC_STEP_IDS]


def options_by_section() -> dict:
    """Group options by section for UI."""
    out = {}
    for o in SYNC_OPTIONS:
        out.setdefault(o.section, []).append(o)
    return out


def build_env_overrides_from_args(args: Any) -> dict:
    """Given parsed argparse namespace, return env overrides (env_key -> str value)."""
    overrides = {}
    for o in SYNC_OPTIONS:
        if o.env_key is None:
            continue
        val = getattr(args, o.key, None)
        if val is None:
            continue
        if o.kind == "bool":
            overrides[o.env_key] = "true" if val else "false"
        elif o.kind == "path" and val is not None:
            overrides[o.env_key] = str(Path(val).resolve())
        else:
            overrides[o.env_key] = str(val)
    return overrides


def build_env_overrides_from_dict(values: dict) -> dict:
    """Given option key -> value dict, return env overrides for subprocess."""
    overrides = {}
    for o in SYNC_OPTIONS:
        if o.env_key is None:
            continue
        val = values.get(o.key)
        if val is None or (o.kind in ("str", "path") and str(val).strip() == ""):
            continue
        if o.kind == "bool":
            overrides[o.env_key] = "true" if val else "false"
        elif o.kind == "path" and val:
            overrides[o.env_key] = str(Path(val).resolve())
        else:
            overrides[o.env_key] = str(val)
    return overrides


def build_parser_args_from_dict(values: dict) -> List[str]:
    """Build argv list from a dict of option key -> value."""
    argv = []
    for o in SYNC_OPTIONS:
        if o.cli_flag is None:
            continue
        val = values.get(o.key)
        if val is None or (o.kind in ("str", "path") and str(val).strip() == ""):
            continue
        if o.kind == "bool":
            if o.cli_negatable:
                argv.append("--no-" + o.cli_flag.lstrip("-") if not val else o.cli_flag)
            else:
                if val:
                    argv.append(o.cli_flag)
        elif o.kind in ("int", "str", "choice", "path"):
            argv.append(o.cli_flag)
            argv.append(str(val))
    return argv


def get_defaults_dict() -> dict:
    """Return option key -> default value for UI/CLI defaults."""
    return {o.key: o.default for o in SYNC_OPTIONS}


def add_sync_arguments(parser: "argparse.ArgumentParser") -> None:
    """Add all sync option arguments to an ArgumentParser. Requires argparse.ArgumentParser."""
    for o in SYNC_OPTIONS:
        if o.cli_flag is None:
            continue
        dest = o.key
        if o.kind == "bool":
            if o.cli_negatable:
                parser.add_argument(o.cli_flag, dest=dest, action="store_true", default=o.default, help=o.help_text)
                parser.add_argument("--no-" + o.cli_flag.lstrip("-"), dest=dest, action="store_false", help=f"Disable: {o.help_text}")
            else:
                parser.add_argument(o.cli_flag, dest=dest, action="store_true", default=o.default, help=o.help_text)
            continue
        if o.kind == "int":
            parser.add_argument(o.cli_flag, dest=dest, type=int, default=o.default, metavar="N", help=o.help_text)
        elif o.kind == "path":
            parser.add_argument(o.cli_flag, dest=dest, type=str, default=o.default, metavar="PATH", help=o.help_text)
        elif o.kind == "choice":
            parser.add_argument(o.cli_flag, dest=dest, choices=o.choices or [], default=o.default, help=o.help_text)
        else:
            parser.add_argument(o.cli_flag, dest=dest, type=str, default=o.default, metavar="STR", help=o.help_text)


def apply_env_overrides_from_args(args: Any) -> None:
    """Set os.environ from parsed args for every option that has env_key."""
    import os
    for o in SYNC_OPTIONS:
        if o.env_key is None:
            continue
        val = getattr(args, o.key, None)
        if val is None:
            continue
        if o.kind == "bool":
            os.environ[o.env_key] = "true" if val else "false"
        elif o.kind == "path" and val:
            os.environ[o.env_key] = str(Path(val).resolve())
        else:
            os.environ[o.env_key] = str(val)

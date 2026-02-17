#!/usr/bin/env python3
"""
Spotify Sync & Yearly Archive Playlists (SpotiM8 v6)

Pipeline maintains yearly archive playlists only (Finds, Top, Discovery per year):
1. sync     – Sync library to local parquet.
2. rename   – Rename playlists that use old prefixes.
3. delete_monthly_and_genre – Remove any legacy automated monthly/genre playlists.
4. consolidate – Ensure yearly playlists exist for each year.
5. update_current_year – Update current year’s Finds/Top/Discovery with new liked/most-played/discovery.
6. descriptions – Update owned playlist descriptions.
7. health_check, insights_report – Optional post-sync reports.

Only adds tracks; never removes. Destructive ops use backups (data/.backups/).

Usage:
    python -m src.scripts.automation.sync
    python -m src.scripts.automation.sync --skip-sync   # Update playlists only
    python -m src.scripts.automation.sync --sync-only  # Sync data only
    python -m src.scripts.automation.sync --steps sync,update_current_year,descriptions

Steps: sync, rename, delete_monthly_and_genre, consolidate, update_current_year, descriptions, health_check, insights_report.

Env: SPOTIPY_CLIENT_ID, SPOTIPY_CLIENT_SECRET; optional .env and --config FILE.
"""

import argparse
import os
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore", message=".*urllib3.*OpenSSL.*", category=UserWarning)
warnings.filterwarnings("ignore", category=UserWarning, module="urllib3")
warnings.filterwarnings("ignore", category=UserWarning, message=".*Converting to PeriodArray.*")

try:
    from dotenv import load_dotenv
    DOTENV_AVAILABLE = True
except ImportError:
    DOTENV_AVAILABLE = False

# Canonical project root (SPOTIM8 directory) and path setup
from src.scripts.common.project_path import get_project_root
PROJECT_ROOT = get_project_root(__file__)
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

if DOTENV_AVAILABLE:
    env_path = PROJECT_ROOT / ".env"
    if env_path.exists():
        load_dotenv(env_path)


def _apply_config_file_early():
    """Apply --config <file> to os.environ before any config import. Optional JSON file with env keys."""
    if "--config" not in sys.argv:
        return
    try:
        i = sys.argv.index("--config")
        if i + 1 >= len(sys.argv):
            return
        path = Path(sys.argv[i + 1])
        if not path.exists():
            return
        import json
        with open(path, encoding="utf-8") as f:
            overrides = json.load(f)
        for k, v in overrides.items():
            if v is not None and k:
                os.environ[k] = str(v)
    except Exception:
        pass


_apply_config_file_early()

# Spotim8 client/sync used inside _sync_impl.workflow; re-exported below for backward compat.
# Import configuration from config module
from src.scripts.automation.config import *

# Import formatting utilities from formatting module
from src.scripts.automation.formatting import format_playlist_name, format_playlist_description, format_yearly_playlist_name

# Import playlist operations from extracted modules
from src.scripts.automation.playlist_creation import create_or_update_playlist
from src.scripts.automation.playlist_update import update_current_year_playlists
from src.scripts.automation.playlist_consolidation import (
    consolidate_old_monthly_playlists,
    delete_automated_monthly_and_genre_playlists,
)

# Import standardized API wrapper
from src.scripts.common.api_wrapper import api_call as standard_api_call, safe_api_call

# Import error handling decorators
from src.scripts.automation.error_handling import handle_errors, retry_on_error, get_logger as get_error_logger

# Import common API helpers
from src.scripts.common.api_helpers import api_call as api_call_helper, chunked as chunked_helper

# Import email notification module
try:
    import importlib.util
    email_notify_path = Path(__file__).parent / "email_notify.py"
    if email_notify_path.exists():
        spec = importlib.util.spec_from_file_location("email_notify", email_notify_path)
        email_notify = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(email_notify)
        send_email_notification = email_notify.send_email_notification
        is_email_enabled = email_notify.is_email_enabled
        EMAIL_AVAILABLE = True
    else:
        EMAIL_AVAILABLE = False
except Exception:
    EMAIL_AVAILABLE = False


# ============================================================================
# SYNC IMPLEMENTATION (SaaS-grade: config, API, catalog, tracks, descriptions)
# ============================================================================
from src.scripts.automation._sync_impl import (
    DATA_DIR,
    get_sync_data_dir,
    LIKED_SONGS_PLAYLIST_ID,
    SPOTIFY_API_PAGINATION_LIMIT,
    API_RATE_LIMIT_MAX_RETRIES,
    MIN_TRACK_ID_LENGTH,
    KEEP_MONTHLY_MONTHS,
    OWNER_NAME,
    BASE_PREFIX,
    ENABLE_MONTHLY,
    ENABLE_MOST_PLAYED,
    ENABLE_DISCOVERY,
    PREFIX_MONTHLY,
    PREFIX_YEARLY,
    PREFIX_MOST_PLAYED,
    PREFIX_DISCOVERY,
    MONTHLY_NAME_TEMPLATE,
    DATE_FORMAT,
    SEPARATOR_MONTH,
    SEPARATOR_PREFIX,
    CAPITALIZATION,
    MONTH_NAMES_SHORT,
    MONTH_NAMES_MEDIUM,
    MONTH_NAMES,
    DESCRIPTION_TEMPLATE,
    SPOTIFY_MAX_DESCRIPTION_LENGTH,
    MOOD_MAX_TAGS,
    DEFAULT_DISCOVERY_TRACK_LIMIT,
    log,
    verbose_log,
    log_step_banner,
    timed_step,
    set_verbose,
    get_log_buffer,
    api_call,
    get_spotify_client,
    _chunked,
    get_existing_playlists,
    get_playlist_tracks,
    get_liked_song_uris,
    get_user_info,
    _invalidate_playlist_cache,
    _playlist_tracks_cache,
    _to_uri,
    _update_playlist_description_with_genres,
    sync_full_library,
    sync_export_data,
    rename_playlists_with_old_prefixes,
    get_most_played_tracks,
    get_time_based_tracks,
    get_repeat_tracks,
    get_discovery_tracks,
)

# Re-export for backward compatibility
from src.scripts.common.config_helpers import parse_bool_env as _parse_bool_env
from src.scripts.automation.sync_options import (
    add_sync_arguments,
    apply_env_overrides_from_args,
    parse_steps,
    requested_unknown_steps,
    SYNC_STEP_IDS,
)

_data_dir_env = os.environ.get("SPOTIM8_DATA_DIR") or os.environ.get("DATA_DIR")


# Workflow: sync_full_library, sync_export_data, rename_playlists_with_old_prefixes,
# get_most_played_tracks, get_discovery_tracks, etc. from _sync_impl.

def main():
    # Load environment variables from .env file if available
    if DOTENV_AVAILABLE:
        env_path = PROJECT_ROOT / ".env"
        if env_path.exists():
            load_dotenv(env_path)
    
    # Clear log buffer at start
    get_log_buffer().clear()
    
    parser = argparse.ArgumentParser(
        description="Sync Spotify library and update playlists (all options overridable via CLI or --config FILE)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python -m src.scripts.automation.sync                    # Full sync + update
    python -m src.scripts.automation.sync --skip-sync        # Update only (fast)
    python -m src.scripts.automation.sync --sync-only        # Sync only, no playlist changes
    python -m src.scripts.automation.sync --steps sync,update_current_year,descriptions
    python -m src.scripts.automation.sync --steps descriptions   # Only update descriptions
    python -m src.scripts.automation.sync --owner-name Me
    python -m src.scripts.automation.sync --config opts.json  # Load options from JSON (env keys)
        """
    )
    parser.add_argument("--config", metavar="FILE", help="JSON file with env key overrides (e.g. PLAYLIST_OWNER_NAME)")
    add_sync_arguments(parser)
    args = parser.parse_args()

    apply_env_overrides_from_args(args)
    from src.scripts.automation import config as _config
    _config.reload_from_env()

    set_verbose(args.verbose)
    if args.verbose:
        verbose_log("Verbose logging enabled - detailed output will be shown")
    
    log("=" * 60)
    log("SpotiM8 v6 — Sync & Yearly Archive Playlists")
    log("=" * 60)
    log(f"Data directory: {get_sync_data_dir()}")
    if _data_dir_env:
        verbose_log(f"  (from SPOTIM8_DATA_DIR / DATA_DIR env)")
    else:
        verbose_log(f"  (default: project/data). Set SPOTIM8_DATA_DIR to use another path.")
    
    success = False
    error = None
    summary = {}
    
    try:
        verbose_log("Initializing Spotify client...")
        sp = get_spotify_client()
        verbose_log("Fetching user info...")
        user = get_user_info(sp)
        log(f"Authenticated as: {user['display_name']} ({user['id']})")
        verbose_log(f"User details: email={user.get('email', 'N/A')}, followers={user.get('followers', {}).get('total', 'N/A')}, product={user.get('product', 'N/A')}")
    except Exception as e:
        log(f"ERROR: Authentication failed: {e}")
        verbose_log(f"Authentication error details: {type(e).__name__}: {str(e)}")
        if args.verbose:
            import traceback
            verbose_log(f"Traceback:\n{traceback.format_exc()}")
        error = e
        _send_email_notification(False, error=error)
        sys.exit(1)
    
    try:
        # Resolve which steps to run (--steps overrides --skip-sync / --sync-only)
        steps_arg = getattr(args, "steps", None)
        steps_to_run = parse_steps(steps_arg)
        unknown = requested_unknown_steps(steps_arg) if steps_arg else []
        if unknown:
            log(f"  Unknown step(s) ignored: {', '.join(unknown)}")
        if steps_to_run is None:
            steps_to_run = []
            if not args.skip_sync:
                steps_to_run.append("sync")
            if not args.sync_only:
                steps_to_run.extend([
                    "rename", "delete_monthly_and_genre", "consolidate",
                    "update_current_year", "descriptions",
                ])
                if _parse_bool_env("ENABLE_HEALTH_CHECK", False):
                    steps_to_run.append("health_check")
                if _parse_bool_env("ENABLE_INSIGHTS_REPORT", False):
                    steps_to_run.append("insights_report")

        verbose_log(f"Configuration: steps={steps_to_run!r}, skip_sync={args.skip_sync}, sync_only={args.sync_only}")
        verbose_log(f"Environment: OWNER_NAME={OWNER_NAME}, BASE_PREFIX={BASE_PREFIX}")

        for step_id in steps_to_run:
            log("")
            if step_id == "sync":
                log(">>> STEP: DATA SYNC <<<")
                with timed_step("Full Library Sync"):
                    sync_success = sync_full_library(force=args.force)
                    summary["sync_completed"] = "Yes" if sync_success else "No"
                    verbose_log(f"Sync completed: success={sync_success}")

            elif step_id == "rename":
                log(">>> STEP: RENAME PLAYLISTS <<<")
                with timed_step("Rename Playlists with Old Prefixes"):
                    rename_playlists_with_old_prefixes(sp)

            elif step_id == "delete_monthly_and_genre":
                log(">>> STEP: CLEANUP LEGACY PLAYLISTS <<<")
                with timed_step("Cleanup legacy automated playlists"):
                    delete_automated_monthly_and_genre_playlists(sp)

            elif step_id == "consolidate":
                log(">>> STEP: ENSURE YEARLY ARCHIVE PLAYLISTS <<<")
                with timed_step("Ensure yearly archive playlists"):
                    consolidate_old_monthly_playlists(sp, keep_last_n_months=0)

            elif step_id == "update_current_year":
                log(">>> STEP: UPDATE CURRENT YEAR <<<")
                with timed_step("Update current year Finds, Top, Discovery"):
                    update_current_year_playlists(sp)

            elif step_id == "descriptions":
                log(">>> STEP: PLAYLIST DESCRIPTIONS <<<")
                with timed_step("Update playlist descriptions"):
                    try:
                        import pandas as _pd
                        sync_data_dir = get_sync_data_dir()
                        playlists_path = sync_data_dir / "playlists.parquet"
                        if not playlists_path.exists():
                            log(f"  playlists.parquet not found at {playlists_path}; skipping description updates")
                        else:
                            log(f"  Using playlists from {playlists_path}")
                            playlists_df = _pd.read_parquet(playlists_path)
                            if "is_owned" not in playlists_df.columns:
                                owned = playlists_df
                            else:
                                owned = playlists_df[playlists_df["is_owned"] == True]
                            n_owned = len(owned)
                            log(f"  Updating descriptions for {n_owned} owned playlist(s)...")
                            for idx, (_, row) in enumerate(owned.iterrows()):
                                pid = row.get("playlist_id") or row.get("id")
                                if pid:
                                    verbose_log(f"  Description update {idx + 1}/{n_owned}: playlist_id={pid}")
                                    _update_playlist_description_with_genres(sp, user["id"], pid, None)
                            log(f"  Description updates complete ({n_owned} playlists processed)")
                    except Exception as e:
                        log(f"  Update all descriptions failed (non-fatal): {e}")
                        verbose_log(f"  Exception: {type(e).__name__}: {e}")

            elif step_id == "health_check":
                log(">>> STEP: HEALTH CHECK <<<")
                with timed_step("Playlist Health Check"):
                    try:
                        from .playlist_organization import get_playlist_organization_report, print_organization_report
                        import pandas as pd
                        playlists_df = pd.read_parquet(DATA_DIR / "playlists.parquet")
                        playlist_tracks_df = pd.read_parquet(DATA_DIR / "playlist_tracks.parquet")
                        tracks_df = pd.read_parquet(DATA_DIR / "tracks.parquet")
                        owned_playlists = (
                            playlists_df[playlists_df["is_owned"] == True].copy()
                            if "is_owned" in playlists_df.columns
                            else playlists_df.copy()
                        )
                        report = get_playlist_organization_report(
                            owned_playlists, playlist_tracks_df, tracks_df
                        )
                        print_organization_report(report)
                    except Exception as e:
                        verbose_log(f"  Health check failed (non-fatal): {e}")

            elif step_id == "insights_report":
                log(">>> STEP: INSIGHTS REPORT <<<")
                with timed_step("Generating Insights Report"):
                    try:
                        from .playlist_intelligence import generate_listening_insights_report
                        import pandas as pd
                        playlists_df = pd.read_parquet(DATA_DIR / "playlists.parquet")
                        playlist_tracks_df = pd.read_parquet(DATA_DIR / "playlist_tracks.parquet")
                        tracks_df = pd.read_parquet(DATA_DIR / "tracks.parquet")
                        streaming_history_df = None
                        streaming_path = DATA_DIR / "streaming_history.parquet"
                        if streaming_path.exists():
                            streaming_history_df = pd.read_parquet(streaming_path)
                        report = generate_listening_insights_report(
                            playlists_df, playlist_tracks_df, tracks_df, streaming_history_df
                        )
                        log("\n" + report)
                    except Exception as e:
                        verbose_log(f"  Insights report failed (non-fatal): {e}")

            else:
                verbose_log(f"  Unknown step skipped: {step_id}")

        log("\n" + "=" * 60)
        log("✅ Complete!")
        log("=" * 60)
        success = True
        
    except Exception as e:
        log(f"ERROR: {e}")
        import traceback
        error_trace = traceback.format_exc()
        log(error_trace)
        error = e
        success = False
    
    finally:
        # Send email notification
        _send_email_notification(success, summary=summary, error=error)
        
        if not success:
            sys.exit(1)


def _send_email_notification(success: bool, summary: dict = None, error: Exception = None):
    """Helper to send email notification with captured logs."""
    if not EMAIL_AVAILABLE:
        log("  ℹ️  Email notifications not available (email_notify.py not found)")
        return
    
    if not is_email_enabled():
        log("  ℹ️  Email notifications disabled (EMAIL_ENABLED not set to true)")
        return
    
    log_output = "\n".join(get_log_buffer())
    
    try:
        log("  📧 Sending email notification...")
        email_sent = send_email_notification(
            success=success,
            log_output=log_output,
            summary=summary or {},
            error=error
        )
        if email_sent:
            log("  ✅ Email notification sent successfully")
        else:
            log("  ⚠️  Email notification failed (check email configuration)")
    except Exception as e:
        # Don't fail the sync if email fails
        log(f"  ⚠️  Email notification error (non-fatal): {e}")
        import traceback
        log(traceback.format_exc())


if __name__ == "__main__":
    main()


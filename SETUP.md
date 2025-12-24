# 🚀 Local Setup Guide

This guide will help you set up Spotim8 to run locally with automated cron jobs.

## Prerequisites

- Python 3.10+ (check with `python3 --version`)
- Spotify Developer Account (free)
- Git (already installed)

## Quick Setup

Run the automated setup script:

```bash
./scripts/setup_local.sh
```

This will:
1. Create a Python virtual environment
2. Install all dependencies
3. Guide you through setting up your Spotify API credentials

## Manual Setup (Alternative)

If you prefer manual setup:

### 1. Create Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate
```

### 2. Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
pip install -e .
```

### 3. Get Spotify API Credentials

1. Go to [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
2. Log in with your Spotify account
3. Click **"Create app"**
4. Fill in:
   - **App name**: Spotim8 (or any name you like)
   - **App description**: Personal Spotify analytics
   - **Redirect URI**: `http://127.0.0.1:8888/callback`
   - Check **"I understand and agree..."**
5. Click **"Save"**
6. Copy your **Client ID** and **Client Secret**

### 4. Create .env File

```bash
cp env.example .env
```

Edit `.env` and add your credentials:

```bash
SPOTIPY_CLIENT_ID=your_client_id_here
SPOTIPY_CLIENT_SECRET=your_client_secret_here
SPOTIPY_REDIRECT_URI=http://127.0.0.1:8888/callback

# Optional: Get refresh token for automated runs (no browser needed)
# Run: python scripts/get_refresh_token.py
SPOTIPY_REFRESH_TOKEN=your_refresh_token_here

# Optional: Customize playlist naming
PLAYLIST_OWNER_NAME=YourName
PLAYLIST_PREFIX=Finds
```

### 5. Get Refresh Token (Recommended for Automation)

For automated runs without browser interaction:

```bash
source venv/bin/activate
python scripts/get_refresh_token.py
```

This will:
- Open your browser for Spotify authorization
- Generate a refresh token
- Show you the token to add to your `.env` file

### 6. Test the Sync

```bash
./scripts/run_sync_local.sh
```

This will:
- Sync your Spotify library to local parquet files
- Update/create monthly playlists
- Update genre playlists

**Note**: First sync can take 1-2+ hours for large libraries. Subsequent syncs are incremental and much faster.

## Cron Job Setup

The cron job is already set up (by `setup_cron.sh`), but you can verify:

```bash
crontab -l
```

It runs daily at 2:00 AM. To change the schedule, edit with:

```bash
crontab -e
```

## Troubleshooting

### Virtual Environment Not Found

If you see "Virtual environment not found":
```bash
./scripts/setup_local.sh
```

### Missing Credentials Error

Make sure your `.env` file exists and has:
- `SPOTIPY_CLIENT_ID`
- `SPOTIPY_CLIENT_SECRET`

### Authentication Issues

1. Make sure your redirect URI matches exactly: `http://127.0.0.1:8888/callback`
2. Get a fresh refresh token: `python scripts/get_refresh_token.py`
3. Check that your Spotify app is not in "Development Mode" with restricted users (if using a free account)

### Sync Takes Too Long

- First sync always takes longest (hours for large libraries)
- Use `--skip-sync` to only update playlists without re-syncing:
  ```bash
  ./scripts/run_sync_local.sh --skip-sync
  ```

### Check Logs

```bash
tail -f logs/sync.log
```

## Environment Variables Reference

| Variable | Required | Description |
|----------|----------|-------------|
| `SPOTIPY_CLIENT_ID` | ✅ Yes | Your Spotify app Client ID |
| `SPOTIPY_CLIENT_SECRET` | ✅ Yes | Your Spotify app Client Secret |
| `SPOTIPY_REDIRECT_URI` | ✅ Yes | Should be `http://127.0.0.1:8888/callback` |
| `SPOTIPY_REFRESH_TOKEN` | ❌ No | For automated runs without browser |
| `PLAYLIST_OWNER_NAME` | ❌ No | Prefix for playlist names (default: "AJ") |
| `PLAYLIST_PREFIX` | ❌ No | Month playlist prefix (default: "Finds") |

## Next Steps

- Check out the [notebooks](notebooks/) for data analysis examples
- Customize playlist names in `.env`
- Run `./scripts/run_sync_local.sh --help` for sync options


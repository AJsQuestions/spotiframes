# 🔑 Spotify API Setup Instructions

Follow these steps to get your API credentials:

## Step 1: Create Spotify Developer App

1. Go to **https://developer.spotify.com/dashboard**
2. Log in with your Spotify account
3. Click **"Create app"** button
4. Fill in the form:
   - **App name**: `Spotim8` (or any name)
   - **App description**: `Personal Spotify analytics and playlist management`
   - **Website**: (can leave blank or use a placeholder)
   - **Redirect URI**: `http://127.0.0.1:8888/callback` ⚠️ **This must match exactly**
   - **What API/SDKs are you planning to use?**: Check "Web API"
   - Check the box: "I understand and agree..."
5. Click **"Save"**

## Step 2: Get Your Credentials

After creating the app:

1. You'll see your app dashboard
2. Click **"Settings"** (gear icon)
3. Find:
   - **Client ID** - Copy this
   - **Client Secret** - Click "View client secret" and copy it

## Step 3: Add Credentials to .env File

Edit the `.env` file in the project root:

```bash
# Open in your editor
nano .env
# or
code .env
# or
vim .env
```

Replace the placeholder values:

```bash
SPOTIPY_CLIENT_ID=your_actual_client_id_here
SPOTIPY_CLIENT_SECRET=your_actual_client_secret_here
SPOTIPY_REDIRECT_URI=http://127.0.0.1:8888/callback
```

## Step 4: Get Refresh Token (Optional but Recommended)

For automated runs without browser interaction:

```bash
source venv/bin/activate
python scripts/get_refresh_token.py
```

This will:
- Open your browser
- Ask you to authorize the app
- Generate a refresh token
- Show you the token to add to `.env`:

```bash
SPOTIPY_REFRESH_TOKEN=your_refresh_token_here
```

## Step 5: Test the Setup

```bash
./scripts/run_sync_local.sh
```

If everything is configured correctly, it will start syncing your library!

---

**Note**: If you have Python 3.9 (the package officially requires 3.10+), the dependencies are installed and it should still work for most operations. If you encounter issues, consider upgrading Python or using pyenv to manage multiple Python versions.


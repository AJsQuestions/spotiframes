#!/bin/bash
# Setup Local Development Environment
#
# This script sets up a virtual environment and guides you through
# configuring your Spotify API credentials.
#
# Usage:
#   ./scripts/setup_local.sh

set -e

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

echo "=" 
echo "Spotim8 Local Setup"
echo "=" 
echo ""

# Step 1: Create virtual environment
echo "📦 Step 1: Setting up virtual environment..."
if [ -d "venv" ] || [ -d ".venv" ]; then
    echo "   ✅ Virtual environment already exists"
    VENV_DIR="venv"
    [ -d ".venv" ] && VENV_DIR=".venv"
else
    echo "   Creating virtual environment..."
    python3 -m venv venv
    VENV_DIR="venv"
    echo "   ✅ Virtual environment created"
fi

# Activate venv
source "$VENV_DIR/bin/activate"

# Step 2: Install dependencies
echo ""
echo "📦 Step 2: Installing dependencies..."
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
pip install -e .
echo "   ✅ Dependencies installed"

# Step 3: Check for .env file
echo ""
echo "🔑 Step 3: Checking for API credentials..."
if [ -f ".env" ]; then
    echo "   ✅ .env file found"
    echo ""
    echo "   Current .env contents:"
    echo "   ────────────────────────"
    grep -E "SPOTIPY_CLIENT_ID|SPOTIPY_CLIENT_SECRET|SPOTIPY_REDIRECT_URI|SPOTIPY_REFRESH_TOKEN|PLAYLIST_" .env 2>/dev/null | sed 's/^/   /' || echo "   (empty or no credentials found)"
    echo "   ────────────────────────"
    echo ""
    read -p "   Do you want to update the .env file? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        UPDATE_ENV=true
    else
        UPDATE_ENV=false
    fi
else
    echo "   ⚠️  No .env file found"
    UPDATE_ENV=true
fi

# Step 4: Guide user through API setup
if [ "$UPDATE_ENV" = true ]; then
    echo ""
    echo "🔑 Step 4: Setting up Spotify API credentials"
    echo ""
    echo "   To get your Spotify API credentials:"
    echo "   1. Go to https://developer.spotify.com/dashboard"
    echo "   2. Log in with your Spotify account"
    echo "   3. Click 'Create app'"
    echo "   4. Fill in app details (name, description, etc.)"
    echo "   5. Add redirect URI: http://127.0.0.1:8888/callback"
    echo "   6. Click 'Save'"
    echo "   7. Copy your 'Client ID' and 'Client Secret'"
    echo ""
    
    # Create or update .env file
    if [ ! -f ".env" ]; then
        cp env.example .env
        echo "   ✅ Created .env file from env.example"
    fi
    
    echo ""
    echo "   Enter your credentials (press Enter to skip updating a value):"
    echo ""
    
    # Get Client ID
    read -p "   Spotify Client ID: " CLIENT_ID
    if [ ! -z "$CLIENT_ID" ]; then
        if [[ "$OSTYPE" == "darwin"* ]]; then
            # macOS
            sed -i '' "s/SPOTIPY_CLIENT_ID=.*/SPOTIPY_CLIENT_ID=$CLIENT_ID/" .env
        else
            # Linux
            sed -i "s/SPOTIPY_CLIENT_ID=.*/SPOTIPY_CLIENT_ID=$CLIENT_ID/" .env
        fi
    fi
    
    # Get Client Secret
    read -p "   Spotify Client Secret: " CLIENT_SECRET
    if [ ! -z "$CLIENT_SECRET" ]; then
        if [[ "$OSTYPE" == "darwin"* ]]; then
            sed -i '' "s/SPOTIPY_CLIENT_SECRET=.*/SPOTIPY_CLIENT_SECRET=$CLIENT_SECRET/" .env
        else
            sed -i "s/SPOTIPY_CLIENT_SECRET=.*/SPOTIPY_CLIENT_SECRET=$CLIENT_SECRET/" .env
        fi
    fi
    
    # Optional: Playlist owner name
    read -p "   Playlist Owner Name (optional, press Enter to skip): " OWNER_NAME
    if [ ! -z "$OWNER_NAME" ]; then
        if [[ "$OSTYPE" == "darwin"* ]]; then
            sed -i '' "s/PLAYLIST_OWNER_NAME=.*/PLAYLIST_OWNER_NAME=$OWNER_NAME/" .env
        else
            sed -i "s/PLAYLIST_OWNER_NAME=.*/PLAYLIST_OWNER_NAME=$OWNER_NAME/" .env
        fi
    fi
    
    # Optional: Playlist prefix
    read -p "   Playlist Prefix (optional, default: Finds, press Enter to skip): " PREFIX
    if [ ! -z "$PREFIX" ]; then
        if [[ "$OSTYPE" == "darwin"* ]]; then
            sed -i '' "s/PLAYLIST_PREFIX=.*/PLAYLIST_PREFIX=$PREFIX/" .env
        else
            sed -i "s/PLAYLIST_PREFIX=.*/PLAYLIST_PREFIX=$PREFIX/" .env
        fi
    fi
    
    echo ""
    echo "   ✅ .env file updated"
    echo ""
    echo "   🔐 To get a refresh token for automated runs (optional but recommended):"
    echo "      python scripts/get_refresh_token.py"
    echo "      Then add SPOTIPY_REFRESH_TOKEN to your .env file"
fi

echo ""
echo "=" 
echo "✅ Setup Complete!"
echo "=" 
echo ""
echo "Next steps:"
echo "  1. Activate the virtual environment:"
echo "     source venv/bin/activate"
echo ""
echo "  2. (Optional) Get refresh token for automated runs:"
echo "     python scripts/get_refresh_token.py"
echo ""
echo "  3. Test the sync:"
echo "     ./scripts/run_sync_local.sh"
echo ""
echo "  4. The cron job is already set up to run daily at 2:00 AM"
echo ""


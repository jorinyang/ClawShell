#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────
# ClawShell — Obsidian Self-hosted LiveSync Auto-Config
# Backend: CouchDB on clawshell.club/couchdb
# ─────────────────────────────────────────────────────────────────
set -e

COUCHDB_URL="${CLAWSHELL_COUCHDB_URL:-https://clawshell.club/couchdb}"
COUCHDB_USER="${CLAWSHELL_COUCHDB_USER:-admin}"
COUCHDB_PASS="${CLAWSHELL_COUCHDB_PASS:-ClawShell2026!Couch}"
COUCHDB_DB="${CLAWSHELL_COUCHDB_DB:-obsidian}"
PLUGIN_ID="obsidian-livesync"
VAULT="${1:-}"

# ── Detect Obsidian ─────────────────────────────────────────────

detect_obsidian() {
    echo "🔍 Detecting Obsidian..."
    
    # macOS
    if [ -d "/Applications/Obsidian.app" ]; then
        echo "  ✓ macOS: /Applications/Obsidian.app"
        return 0
    fi
    
    # Linux (AppImage / flatpak / snap)
    if command -v obsidian &>/dev/null; then
        echo "  ✓ CLI: obsidian"
        return 0
    fi
    if [ -d "$HOME/.local/share/obsidian" ]; then
        echo "  ✓ Linux: ~/.local/share/obsidian"
        return 0
    fi
    
    # Windows (via WSL / direct)
    OBS_WIN="$APPDATA/obsidian"
    if [ -n "$APPDATA" ] && [ -d "$OBS_WIN" ]; then
        echo "  ✓ Windows: $OBS_WIN"
        return 0
    fi
    
    # Check WSL path
    WIN_USER=$(wslpath "$(powershell.exe -Command '[Environment]::GetFolderPath("LocalApplicationData")' 2>/dev/null | tr -d '\r')" 2>/dev/null)
    if [ -n "$WIN_USER" ] && [ -d "$WIN_USER/obsidian" ]; then
        echo "  ✓ WSL→Windows: $WIN_USER/obsidian"
        return 0
    fi
    
    echo "  ✗ Obsidian not detected"
    return 1
}

# ── Find Vaults ─────────────────────────────────────────────────

find_vaults() {
    local found=()
    
    # macOS
    if [ -d "$HOME/Library/Mobile Documents/iCloud~md~obsidian/Documents" ]; then
        for d in "$HOME/Library/Mobile Documents/iCloud~md~obsidian/Documents"/*/; do
            [ -d "$d" ] && found+=("$d")
        done
    fi
    
    # Linux / WSL
    for d in "$HOME"/*/; do
        if [ -d "${d}.obsidian" ]; then
            found+=("$d")
        fi
    done
    for d in "$HOME/Documents"/*/; do
        if [ -d "${d}.obsidian" ]; then
            found+=("$d")
        fi
    done
    
    # obsidian.json tracks recent vaults
    local obs_json=""
    for p in \
        "$HOME/.config/obsidian/obsidian.json" \
        "$HOME/Library/Application Support/obsidian/obsidian.json" \
        "$HOME/AppData/Roaming/obsidian/obsidian.json"; do
        [ -f "$p" ] && obs_json="$p" && break
    done
    
    if [ -n "$obs_json" ]; then
        while IFS= read -r path; do
            [ -d "$path" ] && found+=("$path")
        done < <(python3 -c "
import json,sys
try:
    d=json.load(open('$obs_json'))
    for v in d.get('vaults',{}).values():
        print(v.get('path',''))
except: pass
" 2>/dev/null)
    fi
    
    printf '%s\n' "${found[@]}"
}

# ── Write LiveSync Config ───────────────────────────────────────

write_config() {
    local vault="$1"
    local plugin_dir="$vault/.obsidian/plugins/$PLUGIN_ID"
    mkdir -p "$plugin_dir"
    
    cat > "$plugin_dir/data.json" << DATAEOF
{
  "couchDB_URI": "${COUCHDB_URL}",
  "couchDB_USER": "${COUCHDB_USER}",
  "couchDB_PASSWORD": "${COUCHDB_PASS}",
  "couchDB_DBNAME": "${COUCHDB_DB}",
  "syncOnSave": true,
  "syncOnStart": true,
  "syncOnFileOpen": false,
  "syncInterval": 0,
  "liveSync": true,
  "periodicReplication": true,
  "batch_size": 50,
  "batches_limit": 40,
  "readChunksOnline": true,
  "syncAfterMerge": true,
  "useHistory": true,
  "versioning": true,
  "versionCount": 20,
  "doNotDeleteFolder": false,
  "disableMarkdownAutoMerge": true,
  "writeDocumentsIfConflicted": false,
  "trashInsteadDelete": true
}
DATAEOF

    # Enable plugin in community-plugins.json
    local comm_file="$vault/.obsidian/community-plugins.json"
    if [ -f "$comm_file" ]; then
        python3 -c "
import json
with open('$comm_file') as f:
    d = json.load(f)
if '$PLUGIN_ID' not in d:
    d.append('$PLUGIN_ID')
with open('$comm_file','w') as f:
    json.dump(d, f, indent=2)
" 2>/dev/null
    else
        echo "[\"$PLUGIN_ID\"]" > "$comm_file"
    fi
    
    echo "  ✅ LiveSync configured → $vault"
}

# ── Verify Connection ───────────────────────────────────────────

verify_connection() {
    echo ""
    echo "🔗 Testing CouchDB connection..."
    
    local resp
    resp=$(curl -sk --max-time 10 -u "${COUCHDB_USER}:${COUCHDB_PASS}" \
        "${COUCHDB_URL}/" 2>&1)
    
    if echo "$resp" | grep -q '"couchdb":"Welcome"'; then
        echo "  ✅ CouchDB: Connected"
    else
        echo "  ⚠️  CouchDB: Connection failed"
        echo "     URL: $COUCHDB_URL"
        return 1
    fi
    
    resp=$(curl -sk --max-time 10 -u "${COUCHDB_USER}:${COUCHDB_PASS}" \
        "${COUCHDB_URL}/${COUCHDB_DB}" 2>&1)
    if echo "$resp" | grep -q '"db_name"'; then
        echo "  ✅ Database: $COUCHDB_DB ready"
    else
        echo "  ⚠️  Database: $COUCHDB_DB not found (will be created on first sync)"
    fi
}

# ── Summary ─────────────────────────────────────────────────────

show_summary() {
    echo ""
    echo "═══════════════════════════════════════════════════"
    echo "  ClawShell Obsidian LiveSync — Setup Complete"
    echo "═══════════════════════════════════════════════════"
    echo ""
    echo "  Server:   $COUCHDB_URL"
    echo "  Database: $COUCHDB_DB"
    echo "  User:     $COUCHDB_USER"
    echo ""
    echo "  Next steps:"
    echo "  1. Open Obsidian → Settings → Community Plugins"
    echo "  2. Enable 'Self-hosted LiveSync'"
    echo "  3. Click the LiveSync ribbon icon → 'Start Sync'"
    echo ""
    echo "  Multi-device: Repeat on other devices, same config."
    echo "═══════════════════════════════════════════════════"
}

# ── Main ────────────────────────────────────────────────────────

echo "╔══════════════════════════════════════════════════╗"
echo "║  ClawShell → Obsidian LiveSync Setup           ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""

if ! detect_obsidian; then
    echo ""
    echo "⚠️  Obsidian not installed. Install from: https://obsidian.md/download"
    echo "    After installation, re-run this script."
    exit 1
fi

# If vault specified, use it
if [ -n "$VAULT" ] && [ -d "$VAULT/.obsidian" ]; then
    write_config "$VAULT"
    verify_connection
    show_summary
    exit 0
fi

if [ -n "$VAULT" ]; then
    echo "❌ Not a valid Obsidian vault: $VAULT"
    echo "   (missing .obsidian directory)"
    exit 1
fi

# Auto-detect vaults
echo ""
echo "📂 Detecting Obsidian vaults..."
mapfile -t vaults < <(find_vaults | sort -u)

if [ ${#vaults[@]} -eq 0 ]; then
    echo "  No vaults detected."
    echo ""
    echo "  Usage: $0 <path/to/vault>"
    echo "  Example: $0 ~/Documents/MyNotes"
    exit 1
fi

echo "  Found ${#vaults[@]} vault(s):"
for i in "${!vaults[@]}"; do
    echo "    $((i+1)). ${vaults[$i]}"
done
echo ""

read -p "Configure ALL found vaults? [Y/n]: " CONFIRM
CONFIRM=${CONFIRM:-Y}
if [[ "$CONFIRM" =~ ^[Yy]$ ]]; then
    for v in "${vaults[@]}"; do
        write_config "$v"
    done
else
    read -p "Enter vault number(s) to configure (e.g. 1,2): " CHOICES
    IFS=',' read -ra NUMS <<< "$CHOICES"
    for n in "${NUMS[@]}"; do
        n=$((n-1))
        if [ -n "${vaults[$n]}" ]; then
            write_config "${vaults[$n]}"
        fi
    done
fi

verify_connection
show_summary

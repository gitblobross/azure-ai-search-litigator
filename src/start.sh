#!/usr/bin/env sh
set -e  # abort on error

root="$(pwd)"
backendPath="$root/src/backend"
frontendPath="$root/src/frontend"
azurePath="$root/.azure"

# --------------------------------------------------------------------
# 1. Locate the azd-generated .env file (first match only)
# --------------------------------------------------------------------
envFile="$(find "$azurePath" -type f -name '.env' | head -n 1)"

if [ -z "$envFile" ] || [ ! -f "$envFile" ]; then
  echo "❌  No .env found under $azurePath – run 'azd up' first."
  exit 1
fi

echo "✅  Found azd .env: $envFile"

# --------------------------------------------------------------------
# 2. Export everything in .env into the shell
# --------------------------------------------------------------------
set -a
. "$envFile"
set +a

# --------------------------------------------------------------------
# 3. (Optional) overlay values from 'azd env get-values' if azd ≥ 1.0
# --------------------------------------------------------------------
if command -v azd >/dev/null; then
  azdJson="$(azd env get-values --output json 2>/dev/null || true)"
  if echo "$azdJson" | grep -q '^{'; then
    if ! command -v jq >/dev/null; then
      echo "⚠️  jq not installed; skipping azd overlay."
    else
      echo "🔄  Overlaying variables from azd environment"
      eval "$(echo "$azdJson" | jq -r 'to_entries|.[]|"export \(.key)=\(.value)"')"
    fi
  fi
fi

# --------------------------------------------------------------------
# 4. Build frontend (if present)
# --------------------------------------------------------------------
if [ -d "$frontendPath" ]; then
  echo "▶️  Installing & building frontend"
  (cd "$frontendPath" && npm install && npm run build)
else
  echo "ℹ️  No frontend directory – skipping npm build"
fi

# --------------------------------------------------------------------
# 5. Create Python venv & install deps
# --------------------------------------------------------------------
echo "🐍  Creating virtualenv"
python3 -m venv .venv
.venv/bin/python -m pip --quiet install -r "$backendPath/requirements.txt"

# --------------------------------------------------------------------
# 6. Launch FastAPI with Uvicorn (hot-reload on code changes)
# --------------------------------------------------------------------
echo "🚀  Starting FastAPI"


# Use Python directly with aiohttp's runner (since this is not FastAPI/ASGI)
exec .venv/bin/uvicorn app:app \
     --app-dir "$backendPath" \
     --host 0.0.0.0 --port 5000 --reload






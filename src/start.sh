#!/usr/bin/env sh
set -e  # abort on any error

root="$(pwd)"
backendPath="$root/src/backend"
frontendPath="$root/src/frontend"
azurePath="$root/.azure"
venvPath="$root/.venv"

# -----------------------------------------------------------
# 0.  Make sure Python can import  src.*  from anywhere
# -----------------------------------------------------------
export PYTHONPATH="${PYTHONPATH}:${root}"

# -----------------------------------------------------------
# 1.  Locate the azd-generated .env (first match)
# -----------------------------------------------------------
envFile="$(find "$azurePath" -type f -name '.env' | head -n 1)"
if [ -z "$envFile" ] || [ ! -f "$envFile" ]; then
  echo "❌  No .env found under $azurePath – run 'azd up' first."
  exit 1
fi
echo "✅  Found azd .env: $envFile"

set -a && . "$envFile" && set +a   # export everything

# -----------------------------------------------------------
# 2.  Overlay azd env (if jq + azd available)
# -----------------------------------------------------------
if command -v azd >/dev/null; then
  if azdJson="$(azd env get-values --output json 2>/dev/null)" && echo "$azdJson" | grep -q '^{'; then
    if command -v jq >/dev/null; then
      echo "🔄  Overlaying variables from azd environment"
      eval "$(echo "$azdJson" | jq -r 'to_entries|.[]|"export \(.key)=\(.value)"')"
    else
      echo "⚠️  jq not installed; skipping azd overlay."
    fi
  fi
fi

# -----------------------------------------------------------
# 3.  Build the frontend (if present)
# -----------------------------------------------------------
if [ -d "$frontendPath" ]; then
  echo "▶️  Installing & building frontend"
  (cd "$frontendPath" && npm install && npm run build)
else
  echo "ℹ️  No frontend directory – skipping npm build"
fi

# -----------------------------------------------------------
# 4.  Create venv & install deps (if not yet created)
# -----------------------------------------------------------
if [ ! -d "$venvPath" ]; then
  echo "🐍  Creating virtualenv"
  python3 -m venv "$venvPath"
  "$venvPath/bin/pip" install --quiet -r "$backendPath/requirements.txt"
fi

# -----------------------------------------------------------
# 5.  Launch FastAPI with hot-reload
# -----------------------------------------------------------
echo "🚀  Starting FastAPI"
exec "$venvPath/bin/uvicorn" src.backend.app:app \
     --reload \
     --host 0.0.0.0 --port 5000 \
     --app-dir "$root"

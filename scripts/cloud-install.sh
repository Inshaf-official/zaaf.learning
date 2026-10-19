#!/usr/bin/env bash
set -euo pipefail
cd /workspace/zaaf.learning
# Each cloud task is isolated. Use this checkout; do not create a worktree.
python3.12 -m venv /workspace/zaaf-venv
/workspace/zaaf-venv/bin/pip install -r backend/requirements.lock
npm ci --prefix frontend --cache /workspace/.npm-cache
python3.12 - <<'PY'
from pathlib import Path
import secrets
path = Path('/workspace/zaaf-cloud.env')
if not path.exists():
    with path.open('x') as stream:
        stream.write('DJANGO_SECRET_KEY=' + secrets.token_hex(48) + '\n')
        stream.write('DEBUG=true\nDATABASE_URL=postgresql://institution:local-development-only@127.0.0.1:5432/institution\n')
        stream.write('ALLOWED_HOSTS=localhost,127.0.0.1\nFRONTEND_ORIGINS=http://localhost:5173,http://127.0.0.1:5173\n')
        stream.write('EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend\n')
    path.chmod(0o600)
PY
if docker container inspect zaaf-phase1-db >/dev/null 2>&1; then
  docker start zaaf-phase1-db >/dev/null
else
  docker run -d --name zaaf-phase1-db -e POSTGRES_DB=institution -e POSTGRES_USER=institution -e POSTGRES_PASSWORD=local-development-only -p 127.0.0.1:5432:5432 postgres:16.6-alpine >/dev/null
fi
for attempt in $(seq 1 30); do
  if docker exec zaaf-phase1-db pg_isready -U institution >/dev/null 2>&1; then break; fi
  sleep 1
done
set -a
source /workspace/zaaf-cloud.env
set +a
export XDG_CACHE_HOME=/workspace/.cache
mkdir -p "$XDG_CACHE_HOME"
if docker container inspect zaaf-redis >/dev/null 2>&1; then
  docker start zaaf-redis >/dev/null
else
  docker run -d --name zaaf-redis -p 127.0.0.1:6379:6379 redis:7.4-alpine >/dev/null
fi
export REDIS_URL=redis://127.0.0.1:6379/0
cd backend
/workspace/zaaf-venv/bin/python manage.py collectstatic --noinput > /tmp/zaaf-static.log
/workspace/zaaf-venv/bin/python manage.py migrate --noinput
/workspace/zaaf-venv/bin/python manage.py check
cd ../frontend
npm run build

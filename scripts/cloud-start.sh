#!/usr/bin/env bash
set -euo pipefail
cd /workspace/zaaf.learning
# Use the existing isolated checkout. Never create an additional worktree.
set -a
source /workspace/zaaf-cloud.env
set +a
export XDG_CACHE_HOME=/workspace/.cache
mkdir -p "$XDG_CACHE_HOME"
docker start zaaf-phase1-db >/dev/null
for attempt in $(seq 1 30); do
  if docker exec zaaf-phase1-db pg_isready -U institution >/dev/null 2>&1; then break; fi
  sleep 1
done
if docker container inspect zaaf-redis >/dev/null 2>&1; then
  docker start zaaf-redis >/dev/null
else
  docker run -d --name zaaf-redis -p 127.0.0.1:6379:6379 redis:7.4-alpine >/dev/null
fi
export REDIS_URL=redis://127.0.0.1:6379/0
cd backend
/workspace/zaaf-venv/bin/python manage.py collectstatic --noinput > /tmp/zaaf-static.log
/workspace/zaaf-venv/bin/python manage.py migrate --noinput
if ! curl --fail --silent http://127.0.0.1:8000/api/auth/csrf/ >/dev/null; then
  nohup /workspace/zaaf-venv/bin/python manage.py runserver 0.0.0.0:8000 --noreload > /tmp/zaaf-backend.log 2>&1 &
  echo $! > /tmp/zaaf-backend.pid
fi
if ! pgrep -f '^/workspace/zaaf-venv/bin/python.*/workspace/zaaf-venv/bin/celery -A config worker' >/dev/null; then
 nohup /workspace/zaaf-venv/bin/celery -A config worker --pool=solo --loglevel=INFO > /tmp/zaaf-worker.log 2>&1 &
 echo $! > /tmp/zaaf-worker.pid
fi
if ! pgrep -f '^/workspace/zaaf-venv/bin/python.*/workspace/zaaf-venv/bin/celery -A config beat' >/dev/null; then
 nohup /workspace/zaaf-venv/bin/celery -A config beat --schedule=/tmp/zaaf-celerybeat --loglevel=INFO > /tmp/zaaf-beat.log 2>&1 &
 echo $! > /tmp/zaaf-beat.pid
fi
cd ../frontend
if ! curl --fail --silent http://127.0.0.1:5173/ >/dev/null; then
  nohup npm run dev -- --strictPort > /tmp/zaaf-frontend.log 2>&1 &
  echo $! > /tmp/zaaf-frontend.pid
fi
for attempt in $(seq 1 30); do
  if curl --fail --silent http://127.0.0.1:8000/api/auth/csrf/ >/dev/null && curl --fail --silent http://127.0.0.1:5173/ >/dev/null; then exit 0; fi
  sleep 1
done
printf '%s\n' 'Startup failed: inspect /tmp/zaaf-backend.log and /tmp/zaaf-frontend.log' >&2
exit 1

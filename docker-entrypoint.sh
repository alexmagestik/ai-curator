#!/bin/sh
set -e

mkdir -p /app/data /app/vector_store /app/knowledge_base_md /app/logs

# Bind mounts from the host may arrive with restrictive permissions.
chmod -R ugo+rwx /app/data /app/vector_store /app/knowledge_base_md /app/logs 2>/dev/null || true

exec "$@"

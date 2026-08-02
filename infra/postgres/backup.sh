#!/bin/sh
set -eu

backup_dir="${BACKUP_DIR:-/backups}"
backup_prefix="${BACKUP_PREFIX:-sahaayak}"
retention_days="${BACKUP_RETENTION_DAYS:-14}"
interval="${BACKUP_INTERVAL_SECONDS:-86400}"
mkdir -p "$backup_dir"

while true; do
  timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
  target="$backup_dir/$backup_prefix-$timestamp.dump"
  echo "creating PostgreSQL backup $target"
  pg_dump --format=custom --file="$target"
  find "$backup_dir" -type f -name "$backup_prefix-*.dump" -mtime "+$retention_days" -delete
  echo "backup complete; retained files: $(find "$backup_dir" -type f -name "$backup_prefix-*.dump" | wc -l | tr -d ' ')"
  sleep "$interval"
done

#!/bin/sh

python=$1
expire_status=0
cleanup_status=0

"$python" -m flask --app alma_duplicate.ui.app:create_app purge-expired-browser-assessments ||
    expire_status=$?
"$python" -m flask --app alma_duplicate.ui.app:create_app cleanup-browser-artifacts ||
    cleanup_status=$?

if [ "$expire_status" -ne 0 ]; then
    exit "$expire_status"
fi
exit "$cleanup_status"

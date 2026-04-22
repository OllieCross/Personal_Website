#!/bin/sh
# Print the current visitor statistics markdown
docker compose exec -T tracker cat /data/visitors.md 2>/dev/null || echo "No stats yet — tracker may still be starting up."

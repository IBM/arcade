#!/bin/bash
set -euo pipefail
IFS=$'\n\t'

# do not run init script at each container strat but only at the first start
if [ ! -f /data/neo4j-import-done.flag ]; then
    neo4j-admin load --from=/data/arcade.dump --database=neo4j --force
    touch /data/neo4j-import-done.flag
else
    echo "The import has already been made."
fi

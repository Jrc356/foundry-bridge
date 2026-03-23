#!/bin/bash

# This script is used to load the initial data into the database.
# It should be run after the database has been created and the schema has been set up.

# docker compose has a note cadence of 1 minute, so we will wait 1 minute between each
# script to ensure that the previous script has loaded and notes generated 
# before starting the next one.

set -eou pipefail

scripts=$(ls seeds/01*.sql | sort)
for script in $scripts; do
  echo "Running $script..."
  docker exec -i foundry-postgres psql -U foundry -d foundry_bridge < $script
  echo "Finished $script. Waiting for 1.5 minutes before running the next script..."
  sleep 90
done

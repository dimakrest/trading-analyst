#!/bin/bash
# Create test database for pytest
set -e
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE DATABASE trading_analyst_test;
    GRANT ALL PRIVILEGES ON DATABASE trading_analyst_test TO $POSTGRES_USER;
EOSQL

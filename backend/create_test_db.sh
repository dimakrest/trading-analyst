#!/bin/bash
# Create test database for pytest if it doesn't exist
# This script runs during postgres container initialization

set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    SELECT 'CREATE DATABASE trading_analyst_test'
    WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'trading_analyst_test')\gexec
EOSQL

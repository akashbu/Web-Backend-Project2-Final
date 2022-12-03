#!/bin/sh

echo "Initializing databases..."
python3 ./bin/init_db.py

echo "Populating Database....."
sqlite3 ./database/primary/mount/games.db < ./share/games.sql
sqlite3 ./database/users.db < ./share/users.sql

echo "Finished Initialization and Population."

exit
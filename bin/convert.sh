#!/bin/bash
# Wait to make sure everything loads okay
sleep 5
echo "Running Spotify to Discogs script..."

# Log runs to make sure that it does on startups
TIMESTAMP=`date "+%Y-%m-%d %H:%M:%S"`
echo "$TIMESTAMP - program was run " >> /home/{USERNAME}/{PATH}/{TO}/{FOLDER}/log/script_log.txt

# Move into program directory
cd /home/{USERNAME}/{PATH}/{TO}/{FOLDER}

# Activate environment and run
source /home/{USERNAME}/{PATH}/{TO}/{FOLDER}/env/bin/activate
/home/{USERNAME}/{PATH}/{TO}/{FOLDER}/env/bin/python3 main.py

# Deactivae environment and keep terminal open
deactivate
bash

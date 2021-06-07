#!/bin/bash
# Wait to make sure everything loads okay
sleep 5
echo "Running Spotify to Discogs script..."

# Log runs to make sure that it does on startups
TIMESTAMP=`date "+%Y-%m-%d %H:%M:%S"`
echo "$TIMESTAMP - program was run" >> /{PATH}/{TO}/{FOLDER}/logs/script.log

# Move into program directory
cd /{PATH}/{TO}/{FOLDER}

# Activate environment and run
source /{PATH}/{TO}/{FOLDER}/env/bin/activate
if /{PATH}/{TO}/{FOLDER}/env/bin/python3 main.py ; then
    TIMESTAMP=`date "+%Y-%m-%d %H:%M:%S"`
    echo "$TIMESTAMP - program succeded" >> /{PATH}/{TO}/{FOLDER}/logs/script.log
else
    TIMESTAMP=`date "+%Y-%m-%d %H:%M:%S"`
    echo "$TIMESTAMP - program failed" >> /{PATH}/{TO}/{FOLDER}/logs/script.log
fi

# Deactivate environment and keep terminal open
deactivate
bash

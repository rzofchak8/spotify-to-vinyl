#!/bin/bash
# Wait 5 seconds to make sure everything loads okay
sleep 5

# Log runs to make sure that it does on startups
TIMESTAMP=`date "+%Y-%m-%d %H:%M:%S"`
echo "$TIMESTAMP - program was run" >> /{PATH}/{TO}/spotify-to-vinyl/logs/script.log

# Move into program directory
cd /{PATH}/{TO}/spotify-to-vinyl

# Activate environment and run; create virtual environment if necessary
if [ ! -d /{PATH}/{TO}/spotify-to-vinyl/env ]; then
    echo "Downloading requirements..."
    python3 -m venv env
    source /{PATH}/{TO}/spotify-to-vinyl/env/bin/activate
    pip install -r requirements.txt
else
    source /{PATH}/{TO}/spotify-to-vinyl/env/bin/activate
fi

echo "Running Spotify to Discogs script..."

# Run program and log result
if /{PATH}/{TO}/spotify-to-vinyl/env/bin/python3 main.py ; then
    TIMESTAMP=`date "+%Y-%m-%d %H:%M:%S"`
    echo "$TIMESTAMP - program was successful" >> /{PATH}/{TO}/spotify-to-vinyl/logs/script.log
else
    TIMESTAMP=`date "+%Y-%m-%d %H:%M:%S"`
    echo "$TIMESTAMP - program failed" >> /{PATH}/{TO}/spotify-to-vinyl/logs/script.log
fi

# Deactivate environment and keep terminal open
deactivate
sleep 5
exit

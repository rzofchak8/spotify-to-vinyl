"""Driver file."""

# Standard imports
import os
import json
import logging
import logging.config

# Local imports
from utils.core import (
    setup,
    get_spotify_session,
    get_discogs_username,
    find_user_playlist,
    get_albums,
    make_vinyl_list,
    discogs_get,
    find_proper_id,
)

logger = logging.getLogger('')


def main():
    """Driver function."""
    # Init logger
    logging_config = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'standard': {
                'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
            },
        },
        'handlers': {
            'default_handler': {
                'class': 'logging.FileHandler',
                'level': 'INFO',
                'formatter': 'standard',
                'filename': os.path.join('logs', 'application.log'),
                'encoding': 'utf8'
            },
        },
        'loggers': {
            '': {
                'handlers': ['default_handler'],
                'level': 'INFO',
                'propagate': False
            }
        }
    }
    logging.config.dictConfig(logging_config)

    # If credentials file does not exist create it
    if not os.path.isfile("credentials.json"):
        open("credentials.json", 'x')
        user_creds = {}

    # Else, we can load the credential file in
    else:
        with open("credentials.json", 'r') as infile:
            user_creds = json.load(infile)

    # setup files necessary for info storage
    playlist_name, song_count = setup()

    # start spotify session
    sp_session = get_spotify_session(user_creds)

    # verify discogs token
    username, user_creds = get_discogs_username(user_creds)

    print("Please be patient, the program speed is limited by Discogs api.")
    print("updating... (large playlists may take a while)")

    # get albums in playlist from spotify
    pid = find_user_playlist(playlist_name, song_count, sp_session)
    get_albums(pid, sp_session)

    # update discogs wantlist
    make_vinyl_list(song_count, username, user_creds)

    # write any new data
    with open("credentials.json", 'w') as outfile:
        outfile.write(json.dumps(user_creds, indent=4))

    print("done")
    logger.info("Program finished successfully")


if __name__ == '__main__':
    main()
    
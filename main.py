"""Driver file."""

# Standard imports
import os
import sys
import json
import logging
import logging.config

# Local imports
from utils.core import (
    setup,
    get_discogs_username,
    make_vinyl_list,
    get_album_ids
)

from utils.spotify import (
    spotify_session,
    find_user_playlist,
    get_albums,
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

    with open("credentials.json", 'r') as infile:
        user_creds = json.load(infile)

    # setup files necessary for info storage
    playlist_name, song_count = setup()

    # start spotify session
    sp_session = spotify_session(user_creds)

    if sp_session is None:
        print("Error in session creation. please try again.")
        logger.error("Spotify session getting returned None")
        sys.exit(1)

    # verify discogs token
    username, user_creds = get_discogs_username(user_creds)

    print("\nupdating Spotify playlist...")

    # get albums in playlist from spotify
    pid = find_user_playlist(playlist_name, song_count, sp_session)
    get_albums(pid, sp_session)

    print("\nupdating Discogs wantlist... (large playlists may take a while)")
    print("Please be patient, the program speed is limited by Discogs api.")

    # update discogs wantlist
    make_vinyl_list(song_count, username, user_creds)

    print("done")
    logger.info("Program finished successfully")


if __name__ == '__main__':
    main()

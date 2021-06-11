"""Spotify API-related functions."""
import sys
import json
import uuid
import logging
import time
from datetime import datetime


import spotipy
from spotipy.oauth2 import SpotifyPKCE
from spotipy.exceptions import SpotifyException


# define top level module logger
logger = logging.getLogger(__name__)


def spotify_session(user_creds):
    """Get or instantiate Spotify API session."""
    state = str(uuid.uuid4())

    scope = ("user-library-read playlist-read-private " +
             "playlist-read-collaborative user-library-read user-follow-read")

    try:
        session = spotipy.Spotify(auth_manager=SpotifyPKCE(scope=scope,
                                  client_id=user_creds['spotify_cid'],
                                  redirect_uri=user_creds['spotify_uri'],
                                  state=state))

        logger.info("Acquired Spotify api session")
        return session

    except SpotifyException as err:
        logger.exception(err.reason)
        return None


def find_user_playlist(playlist_name, song_count, sp_api, offset=0):
    """Get specified user playlist from Spotify."""
    try:
        with open("cache.json", 'r') as infile:
            playlist_info = json.load(infile)

        if playlist_info['playlist'].lower() == playlist_name:

            return playlist_info['spotify_id']

    except ValueError:

        playlist_info = {}

    results = sp_api.current_user_playlists(offset=offset)

    # get dict of playlist you are trying to find
    goal = next((sub for sub in results['items']
                 if sub['name'].lower() == playlist_name), None)

    # we widen the search if there are more results and it was not found
    if goal is None:
        if results['next'] is not None:
            find_user_playlist(playlist_name, song_count,
                               sp_api, offset=offset+50)

        else:
            logger.info("Playlist could not be found")
            print("Playlist cannot be found. Please try another playlist " +
                  "(or check spelling).")
            sys.exit(1)

    # playlist found, sanity check to ensure the playlist hasn't been seen
    elif 'id' not in playlist_info or playlist_info['id'] != goal['id']:

        playlist_info = {
            "playlist":       goal['name'],
            "song_count":     song_count,
            "spotify_id":     goal['id'],
            "albums":         [],
            "added":          [],
            "not_in_discogs": []
        }

        # cache playlist info
        with open("cache.json", 'w') as outfile:
            outfile.write(json.dumps(playlist_info, indent=4))

    return goal['id']


def get_album_year(album_ids, albums, sp_api):
    """Get the album release year."""
    # basic rate limiting handling
    while True:
        try:
            results = sp_api.albums(album_ids)
            break

        except SpotifyException as err:
            rate_limit = err.headers['Retry-After']
            time.sleep(rate_limit)

    for obj in results['albums']:

        idx = next(i for i, item in enumerate(albums['albums'])
                   if item['id'] == obj['id'])
        albums['albums'][idx]['year'] = obj['release_date'][:4]

    return [], albums


def get_albums(pid, sp_api, offset=0):
    """Retrieve album information from Spotify api."""
    fields = ("items(added_at, track(album(name, id))," +
              "track.artists(name)), next")

    results = sp_api.playlist_items(pid, fields=fields, offset=offset,
                                    market="from_token",
                                    additional_types=['track'])

    with open("cache.json", 'r') as infile:
        albums = json.load(infile)

    last_time = 0
    if 'time_accessed' in albums:
        last_time = albums['time_accessed']

    # store ids so we can easily get album release year
    album_ids = []

    for item in results['items']:

        timestamp = datetime.strptime(item['added_at'],
                                      '%Y-%m-%dT%H:%M:%SZ').timestamp()
        info = item['track']

        artists = []
        for artist in info['artists']:
            artists.append(artist['name'])

        # ensure that we have not seen this album before
        index = next((i for i, item in enumerate(albums['albums'])
                      if info['album']['id'] == item['id']), None)
        added = next((i for i in (albums['added'] + albums['not_in_discogs'])
                      if info['album']['id'] == i['id']), None)

        # if we have and it is a new song since last check, update song count
        if index is not None and added is None:

            if timestamp > last_time:
                albums['albums'][index]['song_count'] += 1
                albums['albums'][index]['artists'] = list(set(artists) &
                                                          set(albums['albums'][index]['artists']))

        # else, we have a new album
        elif added is None:

            # attempt at stripping different editions of album
            index = info['album']['name'].rfind(" (")
            if index == -1:
                index = len(info['album']['name'])

            album_info = {
                'name':       info['album']['name'][:index],
                'id':         info['album']['id'],
                'song_count': 1,
                'attempts':   0,
                'artists':    artists
            }

            albums['albums'].append(album_info)
            album_ids.append(info['album']['id'])

        # query capped at 20
        if len(album_ids) == 20:
            album_ids, albums = get_album_year(album_ids, albums, sp_api)

    # get remaining album release dates
    if len(album_ids) != 0:
        album_ids, albums = get_album_year(album_ids, albums, sp_api)

    # write data ahead of time to avoid recursive mess
    with open("cache.json", 'w') as outfile:
        outfile.write(json.dumps(albums, indent=4))

    # do again until we have every album in playlist
    if results['next'] is not None:
        get_albums(pid, sp_api, offset=offset+100)

    else:
        albums['time_accessed'] = time.time()
        with open("cache.json", 'w') as outfile:
            outfile.write(json.dumps(albums, indent=4))

    logger.info("Playlist albums updated")

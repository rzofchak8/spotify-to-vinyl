"""Spotify to vinyl API function."""

# Standard library imports
import os
import json
import time
import webbrowser
import socket
import logging
from datetime import datetime

# Third party imports
import spotipy
import requests
import discogs_client
from requests_oauthlib import OAuth1
from spotipy.exceptions import SpotifyException
from spotipy.oauth2 import SpotifyOAuth

# define top level module logger
logger = logging.getLogger(__name__)

def setup():
    """Create initial files and gather variables."""
    if not os.path.isfile("cache.json"):
        open("cache.json", 'x')
        logger.info("Created cache.json")

    try:
        with open("cache.json", 'r') as infile:
            info = json.load(infile)

        playlist_name = info['playlist'].lower()
        criteria = info['song_count']
        logger.info("Loaded info from existing cache.json")

    except (ValueError, KeyError):
        print("Welcome! Please enter a playlist that you want to pull vinyl" +
              " from (you must own or follow this playlist).")
        print("This program will run once a day, on startup.")
        playlist_name = input("playlist name: ").lower()

        criteria = int(input("How many songs from an album should the " +
                             "playlist have for that album to be added to" +
                             " your wishlist? (1-5): "))
        criteria = max(min(criteria, 5), 1)
        logger.exception("Handled new cache info")

    logger.info("Using playlist: %s with %s song(s) needed for discogs",
                playlist_name, str(criteria))
    return playlist_name, criteria


def get_spotify_session(user_creds):
    """Get or instantiate Spotify API session."""
    # TODO: new-user case
    # TODO: store client id and secret in a different manner

    scope = ("user-library-read playlist-read-private " +
             "playlist-read-collaborative user-library-read user-follow-read")

    try:
        session = spotipy.Spotify(auth_manager=SpotifyOAuth(scope=scope,
                                                     client_id=user_creds['spotify_cid'],
                                                     client_secret=user_creds['spotify_csecret'],
                                                     redirect_uri=user_creds['spotify_uri']))
        logger.info("Acquired Spotify api session")
        return session
    
    except SpotifyException as err:
        logger.exception(err.reason)
        return None


def authorize_discogs_user(url, d_api, user_creds):
    """Get authorization credentials for Discogs API."""
    # get the user to authenticate this program
    webbrowser.open(url)

    # we automatically get credentials by listening locally
    sock = socket.socket()
    sock.bind(('localhost', 9002))
    sock.listen()
    sock.settimeout(1)

    logger.info("Bound socket to port 9002")
    while True:
        try:
            conn = sock.accept()[0]
            try:
                data = conn.recv(4096)
                if not data:
                    break
            except socket.timeout:
                continue
            conn.close()
            break
        except socket.timeout:
            continue

    sock.close()

    # scrub data for the verifier
    data = data.decode('utf-8')
    index = data.find("oauth_verifier") + len("oauth_verifier") + 1
    data = data[index:]
    index = data.find(' ')
    verifier = data[:index]

    # TODO: store client id and secret in a different manner
    # authenticate user through discogs api library, save details
    token, secret = d_api.get_access_token(verifier)

    user_creds['user_token'] = token
    user_creds['user_secret'] = secret
    logging.info("Socket closed, discogs credentials gathered")
    return user_creds


# TODO: store client id and secret in a different manner
def get_discogs_session(user_creds):
    """Get or instantiate Discogs API session, return username."""
    try:
        token = user_creds['user_token']
        secret = user_creds['user_secret']

        d_api = discogs_client.Client('my_user_agent/1.0', consumer_key=user_creds['discogs_ckey'],
                                      consumer_secret=user_creds['discogs_csecret'],
                                      token=token, secret=secret)

    except IndexError:

        d_api = discogs_client.Client('my_user_agent/1.0', consumer_key=user_creds['discogs_ckey'],
                                      consumer_secret=user_creds['discogs_csecret'])

        url = d_api.get_authorize_url(user_creds['discogs_auth_url'])[2]
        user_creds = authorize_discogs_user(url, d_api, user_creds)

    logger.info("Acquired Discogs api session")
    url = "https://api.discogs.com/oauth/identity"
    auth = OAuth1(user_creds['discogs_ckey'], user_creds['discogs_csecret'],
                  user_creds['user_token'], user_creds['user_secret'])

    username = requests.get(url, auth=auth).json()

    return username['username'], user_creds


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
    goal = next((sub for sub in results['items'] if sub['name'].lower() == playlist_name), None)

    # we widen the search if there are more results and it was not found
    if goal is None:
        if results['next'] is not None:
            find_user_playlist(playlist_name, song_count, sp_api, offset=offset+50)

        else:
            logger.info("Playlist could not be found")
            print("Playlist cannot be found :(")
            return -1

    # playlist found, sanity check to ensure the playlist hasn't been seen before
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

        idx = next(i for i, item in enumerate(albums['albums']) if item['id'] == obj['id'])
        albums['albums'][idx]['year'] = obj['release_date'][:4]

    return [], albums


def get_albums(pid, sp_api, offset=0):
    """Retrieve album information from Spotify api."""
    fields = "items(added_at, track(album(name, id)), track.artists(name)), next"

    results = sp_api.playlist_items(pid, fields=fields, offset=offset, market="from_token",
                                    additional_types=['track'])

    with open("cache.json", 'r') as infile:
        albums = json.load(infile)

    last_time = 0
    if 'time_accessed' in albums:
        last_time = albums['time_accessed']

    # store ids so we can easily get album release year
    album_ids = []

    for item in results['items']:

        timestamp = datetime.strptime(item['added_at'], '%Y-%m-%dT%H:%M:%SZ').timestamp()
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

            album_info = {
                'name':       info['album']['name'],
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


def get_album_id(album, user_creds, new=True):
    """Retrieve album information from Discogs."""
    # try searching without artist name, as an edge case
    # see: STRFKR
    if not new:
        artist = ""

    else:
        artist = album['artists'][0]

    params = {
        'release_title': album['name'],
        'artist':        artist,
        'year':          album['year'],
        'format':        "Vinyl LP Album",
        'country':       "US",
        'type':          "release"
    }

    # TODO: store client id and secret in a different manner
    url = "https://api.discogs.com/database/search"

    auth = OAuth1(user_creds['discogs_ckey'], user_creds['discogs_csecret'],
                  user_creds['user_token'], user_creds['user_secret'])

    # query each album in discogs api
    search = requests.get(url, params=params, auth=auth).json()

    with open("test.json", 'w') as outfile:
        outfile.write(json.dumps(search, indent=2))

    # return -1 on album dne, but not before trying once more
    if len(search['results']) == 0:

        if not new:
            return -1

        discogs_id = get_album_id(album, user_creds, False)

    # for simplicity, we will take the first result
    else:
        discogs_id = search['results'][0]['id']

    return discogs_id


def add_to_wishlist(album, username, user_creds):
    """Add an album to the user's Discogs wantlist."""
    try:
        discogs_id = album['discogs_id']

    except KeyError:
        discogs_id = get_album_id(album, user_creds)

    # self rate-limiting for discogs api
    time.sleep(0.7)

    # in the case of an album that may end up in Discogs later
    if discogs_id == -1:

        album['attempts'] += 1
        logger.info("Could not find album %s in Discogs library", album['name'])
        # we will try the album 10 times before giving up
        if album['attempts'] > 10:
            album['attempts'] = -1

    # finding a real id allows us to put to wishlist
    else:

        album['discogs_id'] = discogs_id

        # TODO: store client id and secret in a different manner
        auth = OAuth1(user_creds['discogs_ckey'], user_creds['discogs_csecret'],
                      user_creds['user_token'], user_creds['user_secret'])

        url = "https://api.discogs.com/users/" + username + "/wants/" + str(discogs_id)
        results = requests.put(url, auth=auth)

        # for any discogs error we will return -2
        if results.status_code != 201:
            logger.error("Error in adding album %s to playlist", album['name'])
            print("Error in adding album to wishlist")
            album['attempts'] = -2

        else:

            album['attempts'] = 0

    return album


def make_vinyl_list(song_count_criteria, username, user_creds):
    """Iterate through playlist albums to add to wishlist."""
    with open("cache.json", 'r') as infile:
        data = json.load(infile)

    del_index = []

    for album in data['albums']:

        index = data['albums'].index(album)

        # add the album if it fits our criteria, record results
        if album['song_count'] >= song_count_criteria:

            album = add_to_wishlist(album, username, user_creds)

            if album['attempts'] == 0:
                data['added'].append(album)
                del_index.append(index)

            elif album['attempts'] < 0:
                data['not_in_discogs'].append(album)
                del_index.append(index)

    # remove any albums that were added
    for i in sorted(del_index, reverse=True):
        data['albums'].pop(i)

    with open("cache.json", 'w') as outfile:
        outfile.write(json.dumps(data, indent=4))

    logger.info("Discogs wishlist updated")

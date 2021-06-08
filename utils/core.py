"""Spotify to vinyl API function."""

# Standard library imports
import os
import sys
import json
import time
import logging
from datetime import datetime

# Third party imports
import spotipy
import requests
from spotipy.exceptions import SpotifyException
from spotipy.oauth2 import SpotifyOAuth

# define top level module logger
logger = logging.getLogger(__name__)


def discogs_get(url, auth, params=None):
    """Help make GET requests to Discogs api."""
    header = {
        "Authorization": "Discogs token={}".format(auth)
    }

    try:
        response = requests.get(url, params=params, headers=header)
        response.raise_for_status()
        results = response.json()

    except requests.RequestException as request_err:
        response = request_err.response.json()
        logger.error("Requests error for GET request to: %s with error message %s",
                     url, json.dumps(response))

    except ValueError:
        results = None
        logger.error("Request for url: %s returned no values", url)

    # Discogs rate-limit: 60 requests per minute
    time.sleep(1)
    return results


def discogs_put(url, auth):
    """Help make PUT requests to Discogs api."""
    header = {
        "Authorization": "Discogs token={}".format(auth)
    }

    try:
        response = requests.put(url, headers=header)

        response.raise_for_status()

    except requests.RequestException as request_err:
        response = request_err.response.json()

        logger.error("Requests error for GET request to: %s with error message %s",
                     url, json.dumps(response))

    except ValueError:
        response = None

    # Discogs rate-limit: 60 requests per minute
    time.sleep(1)
    return response


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


def get_discogs_username(user_creds):
    """Get or instantiate Discogs API session, return username."""
    try:
        personal_token = user_creds['personal_discogs_user_token']

    except IndexError:
        personal_token = input(("Please enter your Discogs personal access " +
                                "token (this is only saved locally " +
                                "in credentials.json): "))

        user_creds['personal_discogs_user_token'] = personal_token

    url = "https://api.discogs.com/oauth/identity"

    username = discogs_get(url, personal_token)

    if username is None:
        print("Error in finding discogs profile.")
        print("Please make sure your personal access token is correct." +
              " You may need to delete it from credentials.json")
        sys.exit(1)

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
    goal = next((sub for sub in results['items']
                 if sub['name'].lower() == playlist_name), None)

    # we widen the search if there are more results and it was not found
    if goal is None:
        if results['next'] is not None:
            find_user_playlist(playlist_name, song_count,
                               sp_api, offset=offset+50)

        else:
            logger.info("Playlist could not be found")
            print("Playlist cannot be found :(")
            return -1

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


def find_proper_id(items, title):
    """Iterate through results to find correct Discogs album id."""
    owners = -1
    discogs_id = -1
    title = title.replace(" ", "")
    #print(json.dumps(items, indent=2))
    for album in items:

        # title format: artist - title
        index = album['title'].rfind(" - ") + 3

        if (album['community']['have'] > owners and 
            album['title'][index:].lower().replace(" ", "") == title.lower()):
                #print("HERE")
                discogs_id = album['id']
                owners = album['community']['have']

    #print(discogs_id)
    return discogs_id


def get_album_id(album, user_creds, new=True, year_add=0):
    """Retrieve album information from Discogs."""
    # try searching without artist name, as an edge case
    # see: STRFKR
    if not new:
        artist = ""

    else:
        try:
            artist = album['artists'][0]
        except IndexError:
            artist = ""

    params = {
        'release_title': album['name'],
        'artist':        artist,
        'year':          str(int(album['year']) + year_add),
        'format':        "vinyl lp",
        'type':          "release"
    }

    url = "https://api.discogs.com/database/search"

    results = discogs_get(url, 
                          user_creds['personal_discogs_user_token'],
                          params)

    if results is None:
        print("Error in finding album.")
        print("Please make sure your personal access token is correct." +
              " You may need to delete it from credentials.json")
        sys.exit(1)

    # try 4 times
    if len(results['results']) == 0:

        if not new and year_add == 1:
            return -1

        # check the next year
        elif new and year_add == 0:
            discogs_id = get_album_id(album, user_creds, year_add=1)

        # remove the artist
        elif new and year_add == 1:
            discogs_id = get_album_id(album, user_creds, False)
        
        # remove the artist and check the next year
        else:
            discogs_id = get_album_id(album, user_creds, False, 1)

    # need to find most relavant result
    else:
        discogs_id = find_proper_id(results['results'], album['name'].lower())


    return discogs_id


def add_to_wishlist(album, username, user_creds):
    """Add an album to the user's Discogs wantlist."""
    try:
        discogs_id = album['discogs_id']

    except KeyError:
        discogs_id = get_album_id(album, user_creds)

    # in the case of an album that may end up in Discogs later
    if discogs_id == -1:

        album['attempts'] += 1
        logger.info("Could not find album %s in Discogs library",
                    album['name'])

        # we will try the album 14 times before giving up
        if album['attempts'] > 14:
            album['attempts'] = -1

    # finding a real id allows us to put to wishlist
    else:

        album['discogs_id'] = discogs_id

        url = ("https://api.discogs.com/users/" + username
               + "/wants/" + str(discogs_id))

        results = discogs_put(url, user_creds['personal_discogs_user_token'])

        if results.status_code != 201:
            logger.error("Error in PUT request to %s with album %s",
                         url, album['name'])
            print("Error in adding album {} to wishlist".format(album['name']))
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

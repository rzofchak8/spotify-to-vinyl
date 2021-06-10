"""Spotify to vinyl API function."""

# Standard library imports
import os
import sys
import json
import time
import logging

# Third party imports
import requests
import jellyfish

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


def get_discogs_username(user_creds):
    """Get or instantiate Discogs API session, return username."""
    try:
        personal_token = user_creds['personal_discogs_user_token']

    except KeyError:
        personal_token = input(("Please enter your Discogs personal access " +
                                "token (this is only saved locally " +
                                "in credentials.json): "))

        user_creds['personal_discogs_user_token'] = personal_token
        with open("credentials.json", 'w') as outfile:
            outfile.write(json.dumps(user_creds, indent=4))
 
    url = "https://api.discogs.com/oauth/identity"

    username = discogs_get(url, personal_token)

    if username is None:
        print("Error in finding discogs profile.")
        print("Please make sure your personal access token is correct." +
              " You may need to delete it from credentials.json")
        sys.exit(1)

    return username['username'], user_creds


def find_proper_id(items, title):
    """Iterate through results to find correct Discogs album id."""
    owners = -1
    discogs_id = -1
    title = title.replace(" ", "")

    for album in items:

        # title format: artist - title
        index = album['title'].rfind(" - ") + 3

        if (album['community']['have'] > owners and
           album['title'][index:].lower().replace(" ", "") == title.lower()):

            discogs_id = album['id']
            owners = album['community']['have']

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
        if new and year_add == 0:
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

        # we will try the album 5 times before giving up
        if album['attempts'] > 5:
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

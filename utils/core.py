""" Spotify to vinyl functions """

# Standard library imports
import os
import spotipy
import json
import re
import time
import webbrowser
import socket
from datetime import datetime

# Third party imports
import requests
import discogs_client
from requests_oauthlib import OAuth1
from spotipy.oauth2 import SpotifyClientCredentials, SpotifyOAuth


def setup():
    """ Create initial files and gather variables. """
    
    if not os.path.isfile("cache.json"):
        open("cache.json", 'x')

    try:
        with open("cache.json", 'r') as infile:
            info = json.load(infile)

        playlist_name = info['playlist'].lower()
        criteria = info['song_count']

    except (ValueError, KeyError):
        print("Welcome! Please enter a playlist that you want to pull vinyl" +
              " from (you must own or follow this playlist).")
        
        playlist_name = input("playlist name: ").lower()

        criteria = int(input("How many songs from an album should the " + 
                             "playlist have for that album to be added to" + 
                             " your wishlist? (1-5): "))
        criteria = max(min(criteria, 5), 1)
    
    return playlist_name, criteria

def get_spotify_session(user_creds):
    """ Get or instantiate Spotify API session. """

    # TODO: new-user case
    # TODO: store client id and secret in a different manner

    scope = ("user-library-read playlist-read-private " +
            "playlist-read-collaborative user-library-read user-follow-read")

    return spotipy.Spotify(auth_manager=SpotifyOAuth(scope=scope,
                                                     client_id=user_creds['spotify_cid'],
                                                     client_secret=user_creds['spotify_csecret'],
                                                     redirect_uri=user_creds['spotify_uri']))

def authorize_discogs_user(url, d):
    """ Get authorization credentials for Discogs API. """
    
    # get the user to authenticate this program
    webbrowser.open(url)
    
    # we automatically get credentials by listening locally
    s = socket.socket()
    s.bind(("localhost", 9002))

    s.listen()
    s.settimeout(1)
    while True:
        try: 
            c, addr = s.accept()
            try:
                data = c.recv(4096)
                if not data:
                    break
            except socket.timeout:
                continue
            c.close()
            break
        except socket.timeout:
            continue
    s.close()
    
    # scrub data for the verifier
    data = data.decode('utf-8')
    index = data.find("oauth_verifier") + len("oauth_verifier") + 1
    data = data[index:]
    index = data.find(" ")
    verifier = data[:index]

    # authenticate user through discogs api library, save details
    token, secret = d.get_access_token(verifier)
    with open("credentials.txt", 'a') as outfile:
        outfile.write("Token: " + token + '\n')
        outfile.write("Secret: " + secret + '\n')
    
    return token, secret

# TODO: no longer correct implememtation, need to fix
def get_discogs_session(user_creds):
    """ Get or instantiate Discogs API session, return username. """
    
    try:
        token = user_creds['user_token']
        secret = user_creds['user_secret']
        
        d = discogs_client.Client('my_user_agent/1.0', consumer_key=user_creds['discogs_ckey'],
                                  consumer_secret=user_creds['discogs_csecret'],
                                  token=token, secret=secret)

    except IndexError: 
        
        d = discogs_client.Client('my_user_agent/1.0', consumer_key=user_creds['discogs_ckey'],
                                  consumer_secret=user_creds['discogs_csecret'])
        url = d.get_authorize_url(user_creds['discogs_auth_url'])[2]
        
        token, secret = authorize_discogs_user(url, d)

    url = "https://api.discogs.com/oauth/identity"
    auth = OAuth1(user_creds['discogs_ckey'],
                  user_creds['discogs_csecret'], token, secret)
    username = requests.get(url, auth=auth).json()

    return username['username']

def find_user_playlist(playlist_name, song_count, sp, offset=0):
    """ Get specified user playlist from Spotify. """
    
    try:
        with open("cache.json", 'r') as infile:
            playlist_info = json.load(infile)
        if playlist_info['playlist'].lower() == playlist_name:
            return playlist_info['spotify_id']
    except ValueError:
        playlist_info = {}

    results = sp.current_user_playlists(offset=offset)

    # get dict of playlist you are trying to find
    goal = next((sub for sub in results['items'] if sub['name'].lower() == playlist_name), None)

    # we widen the search if there are more results and it was not found
    if goal is None:
        if results['next'] is not None:
            find_user_playlist(playlist_name, sp, offset=offset+50)
        else:
            print("Playlist cannot be found :(")
            return -1

    # playlist found, sanity check to ensure the playlist hasn't been seen before
    elif 'id' not in playlist_info or playlist_info['id'] != goal['id']:  
        playlist_info = {
            "playlist"      : goal['name'],
            "song_count"    : song_count,
            "spotify_id"    : goal['id'],
            "albums"        : [],
            "added"         : [],
            "not_in_discogs": []
        }
            
        # cache playlist info
        with open("cache.json", 'w') as outfile:
            outfile.write(json.dumps(playlist_info, indent=4))

    return goal['id']

def get_albums(pid, sp, offset=0):
    """ Retrieve album information from Spotify api. """
    fields = "items(added_at, track(album(name, id)), track.artists(name)), next"
    
    results = sp.playlist_items(pid, fields=fields, offset=offset, market="from_token", additional_types=['track'])

    with open("cache.json") as infile:
        albums = json.load(infile)

    last_time = 0
    if 'time_accessed' in albums:
        last_time = albums['time_accessed']

    for item in results['items']:
        timestamp = datetime.strptime(item['added_at'], '%Y-%m-%dT%H:%M:%SZ').timestamp()
        info = item['track']

        artists = []
        for artist in info['artists']:
            artists.append(artist['name'])
        
        name = info['album']['name']
        spid = info['album']['id']
        index = next((i for i, item in enumerate(albums['albums']) if spid == item['id']), None)
        added = next((i for i in (albums['added'] + albums['not_in_discogs']) if spid == i['id']), None)
        
        if index is not None and added is None:
            if timestamp > last_time:
                albums['albums'][index]['song_count'] += 1
                albums['albums'][index]['artists'] = list(set(artists) & set(albums['albums'][index]['artists']))
        elif added is None:
            album_info = {
                'name': name,
                'id': spid,
                'song_count': 1,
                'attempts': 0,
                'artists': artists
            }
            albums['albums'].append(album_info)

    with open('cache.json', 'w') as outfile:
        outfile.write(json.dumps(albums, indent=4))
    
    if results['next'] is not None:
        get_albums(pid, sp, offset=offset+100)
    else:
        albums['time_accessed'] = time.time()
        with open('cache.json', 'w') as outfile:
            outfile.write(json.dumps(albums, indent=4))

def get_album_id(album, user_creds):
    """ Retrieve album information from Discogs. """
    
    params = {
        "release_title": album['name'],
        "artist": album['artists'][0],
        "format": "Vinyl",
        "country": "US",
        "type": "release"
    }

    # TODO: fix authentication method 
    url = "https://api.discogs.com/database/search"

    auth = OAuth1(user_creds['discogs_ckey'], user_creds['discogs_csecret'],
                  user_creds['user_token'], user_creds['user_secret'])

    search = requests.get(url, params=params, auth=auth).json()

    # return -1 on album dne
    if len(search['results']) == 0:
        return -1

    # for simplicity, we will take the first result
    discogs_id = search['results'][0]['id']

    return discogs_id

def add_to_wishlist(album, username, user_creds):
    """ Add an album to the user's Discogs wantlist. """
    try:
        discogs_id = album['discogs_id']
    except KeyError:    
        discogs_id = get_album_id(album, user_creds)

    # in the case of an album that may end up in Discogs later
    if discogs_id == -1:
        album['attempts'] += 1
        
        # we will try the album 5 times before giving up 
        if album['attempts'] > 5:
            album['attempts'] = -1
    
    # finding a real id allows us to put to wishlist 
    else:
        album['discogs_id'] = discogs_id

        # TODO: change how we store our consumer key and secret
        auth = OAuth1(user_creds['discogs_ckey'], user_creds['discogs_csecret'],
                      user_creds['user_token'], user_creds['user_secret'])

        url = "https://api.discogs.com/users/" + username + "/wants/" + str(discogs_id)
        results = requests.put(url, auth=auth)

        # for any discogs error we will return -2 
        if results.status_code != 201:
            print("Error in adding album to wishlist")
            album['attempts'] = -2
        
        else:
            album['attempts'] = 0

    return album

def make_vinyl_list(song_count_criteria, username, user_creds):
    """ Iterate through playlist albums to add to wishlist. """
    
    with open('cache.json', 'r') as infile:
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

    for i in sorted(del_index, reverse=True):
        data['albums'].pop(i)
    
    with open('cache.json', 'w') as outfile:
        outfile.write(json.dumps(data, indent=4))

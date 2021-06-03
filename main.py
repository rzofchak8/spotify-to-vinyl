import os
import json
import time

# Local imports
from utils.core import setup, get_spotify_session, get_discogs_session, find_user_playlist, get_albums, make_vinyl_list

if not os.path.isfile("credentials.json"):
    open("credentials.json", 'x')

else:
    with open("credentials.json", 'r') as infile:
        user_creds = json.load(infile)


playlist_name, song_count = setup()

#################### TEMP (TODO: remove later) ####################
sp_id = user_creds['spotify_cid']
sp_secret = user_creds['spotify_csecret']
sp_uri = user_creds['spotify_uri']
d_key = user_creds['discogs_ckey']
d_secret = user_creds['discogs_csecret']
user_token = user_creds['user_token']
user_secret = user_creds['user_secret']
d_auth_url = user_creds['discogs_auth_url']
###################################################################

sp = get_spotify_session(user_creds)

# temp as well
#get_discogs_session(user_creds)
#username = "MastaWayne"
# end temp
username = get_discogs_session(user_creds)

pid = find_user_playlist(playlist_name, song_count, sp)

get_albums(pid, sp)
#exit(0)
make_vinyl_list(song_count, username, user_creds)


print("done")
# Spotify to Vinyl - Local App

This repository contains a Python program that will take albums from a Spotify playlist and add them to your Discogs wantlist.

## How to use

This program is designed to be used on startup, requiring little to no interaction from the user after initialization. 

The program requires 3 items from you: the name of the playlist you want to track, the number of songs per album that the playlist needs to have in order to be followed, and your Discogs personal access token. Once these are supplied, all you need to do is run the [script](bin/convert.sh). The script will:

* Create a virtual environment and install all necessary packages;
* Prompt you for the playlist name, number of songs, and [Discogs token](#Discogs-token);
* Fetch all albums from your playlist;
* Add albums to your Discogs wantlist, if they have enough songs.

You will have to give this program permission to use your Spotify and Discogs accounts to get your playlists and update your wantlists **only**. Your personal credentials are only stored on your local machine in [cache.json](cache.json) and `.cache`, a local file created by Spotify.

## How to set up

1. After cloning, edit [convert.sh](convert.sh) so ALL the **absolute paths** to the files are available. For example: `/{PATH}/{TO}/spotify-to-vinyl/logs/script.log` becomes `/home/rzofchak8/spotify-to-vinyl/logs/script.log`;
2. Make sure the script is executable: `.../spotify-to-vinyl$ chmod +x bin/convert.sh`;
3. Add script to startup processes, if desired. This way, the program runs once on startup and then closes, and you do not have to mess with it ([see OS-specific instructions on startup configuration](#Startup)).

## How to run

Run the script once `./bin/convert/sh` to enter data (playlist name, song count, Discogs token). The first time this program is run will be **much longer** than subsequent runs (see [Limitations](#limitations)).
* If set up properly, you will not have to manually run again. You will see a terminal open to show that the program runs on startup, and that's it!
* If not set to run at startup, simply run the script again! It will only update the playlist data and update your Discogs wantlist from here on out.

## Configuration

### Discogs-token

Your Discogs personal access token can be found in your [Discogs settings](https://www.discogs.com/settings/developers). 
* Under **Just need a personal access token?** select *Generate token*
* Copy and paste that value into the program terminal when prompted, OR
* Add another entry into your [credentials.json](credentials.json) file: `"personal_discogs_user_token": "{YOUR TOKEN HERE}"`

### Startup 

There are different methods per OS to add a program to run on startup:

##### Ubuntu
1. Open **Startup Applications Preferences** from your applications menu;
1. Add a new program, name it **Spotify to Vinyl**;
1. Enter command `gnome-terminal --command '/{ABS PATH}/{TO}/record_proj/bin/convert.sh'`;
1. Hit save.

##### Windows

TODO

##### OS X

TODO
## Limitations

 * Of course, you will need a Spotify account, as well as a Discogs account in order to work.
 * Currently, you must be following the playlist you wish to convert. Private and collaborative playlists should work fine, as long as you follow them. Same goes with any public playlist.
 * Discogs API is rate-limited to [60 queries per minute](https://www.discogs.com/developers/#page:home,header:home-rate-limiting). Unfortunately, this means that this program will run rather slowly, especially on the first execution. When updating, there are far fewer calls to the API that have to be made, so it will be much faster in future executions.
 * Singles will not play well with this program; if the release is not tied to any album, you may get a few random albums in your wantlist because of this.  

## Contribution

Feature requests and issues are welcome via the issues tag on GitHub. Feel free to contribute!

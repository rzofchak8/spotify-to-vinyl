# Spotify to Vinyl - Local App version

This repository contains a Python program that will take albums from a Spotify playlist and add them to your Discogs wantlist.

## How to use

TODO

## Limitations

 * Currently, you must be following the playlist you wish to convert. Private and collaborative playlists should work fine, as long as you follow them. Same goes with any public playlist.
 * Discogs API is rate-limited to [60 queries per minute](https://www.discogs.com/developers/#page:home,header:home-rate-limiting). Unfortunately, this means that this program will run rather slowly, especially on the first execution. When updating, there are far fewer calls to the API that have to be made, so it will be faster in future executions.
 * In relation to the above, there are edge cases that there was an attempt to cover. For example, few artists go under a different name on Spotify than they do on Discogs. Additionally, some releases on vinyl may not be released in the same release year. This program attempts to achieve as many results as possible, and as a result goes slower due to increased Discogs API calls. Unfortuantely, this workaround doesn't catch ever case. Feel free to mess around with this as you see fit.  
 * Singles will not play well with this program; if the release is not tied to any album, you may get a few random albums in your wantlist because of this.  

## How to install
---
TODO

## How to configure and run
---
TODO

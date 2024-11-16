# Autogigification

Generate spotify playlists from setlist.fm!

## Motivation

I've found myself frequently wanting to prepare for a show by listening to the likely setlist.

## Usage

Add the following environment variables to your `.env` file or prepend the command with these variables:

```env
SETLIST_FM_API_KEY=<YOUR_API_KEY>
SPOTIFY_CLIENT_ID=<YOUR_CLIENT_ID>
SPOTIFY_CLIENT_SECRET=<YOUR_CLIENT_SECRET>
SPOTIFY_REDIRECT_URI=http://localhost:3000
SPOTIFY_USERNAME=<YOUR_SPOTIFY_USERNAME>
SETLIST_CACHE=setlist_cache.json
SPOTIFY_TRACK_CACHE=spotify_cache.json
```

Now you can call the command itself.

```sh
ag -b zhu --playlist-name "ZHU 2024" --copy-last-setlist-threshold 7 --max-setlist-length 12
```

This will generate a playlist named "ZHU 2024" containing 12 songs and create it in your spotify account.

If there is a setlist in the last 7 days it will just create a playlist matching that setlist, ignoring songs that aren't by the artist (intro music etc).

If there isn't a recent setlist, it will create a playlist by calculating an exponentially weighted frequency list over the last 20 setlists.  Plus some other features.

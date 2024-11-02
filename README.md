# Autogigification

Generate spotify playlists from setlist.fm

## Motivation

I've found myself frequently wanting to prepare for a show by listening to the likely setlist.


## Usage

```sh
ag -b zhu --playlist-name "ZHU 2024" --copy-last-setlist-threshold 7 --max-setlist-length 12
```

This will generate a playlist named "ZHU 2024" containing 12 songs and create it in your spotify account.

If there is a setlist in the last 7 days it will just create a playlist matching that setlist, ignoring songs that aren't by the artist (intro music etc).

If there isn't a recent setlist, it will create a playlist by calculating an exponentially weighted frequency list over the last 20 setlists.

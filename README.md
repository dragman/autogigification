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
SPOTIFY_REFRESH_TOKEN=<YOUR_SPOTIFY_REFRESH_TOKEN>
SETLIST_CACHE=setlist_cache.json
SPOTIFY_TRACK_CACHE=spotify_cache.json
# Optional: SPOTIFY_SCOPES="playlist-modify-public"
# Optional: SPOTIFY_CACHE_PATH=/tmp/spotify_token_cache
```

Now you can call the command itself.

```sh
ag -b zhu --playlist-name "ZHU 2024" --copy-last-setlist-threshold 7 --max-setlist-length 12
```

This will generate a playlist named "ZHU 2024" containing 12 songs and create it in your spotify account.

If there is a setlist in the last 7 days it will just create a playlist matching that setlist, ignoring songs that aren't by the artist (intro music etc).

If there isn't a recent setlist, it will create a playlist by calculating an exponentially weighted frequency list over the last 20 setlists.  Plus some other features.

### Preview-only mode (no playlist creation)

- Pass `--no-playlist` to the CLI (or `create_playlist: false` in the Lambda payload) to get a JSON response with the setlists that were found/estimated and the Spotify track links so you can build playlists yourself.
- Missing songs are flagged with `status: "not_found"` and are also listed under `missing_songs` per band.
- Each band includes `setlist_type` (`fresh` vs `estimated`) and the date/age of the source setlist so you can visually indicate freshness.
- If a Spotify user token is not configured the CLI/Lambda automatically falls back to this preview mode; a token is only needed for actual playlist creation.
- Force estimation even when a fresh setlist exists with `--force-smart-setlist` (CLI) or `"force_smart_setlist": true` in the Lambda payload.

## Development

- Install deps: `make deps` (uses `.venv`).
- Run unit tests (default marker excludes integration): `make test` or `make test TEST_MARKER="not integration"`.
- Start the local stack (Lambda container + static UI + CORS proxy): `make run` (uses `.env`, exposes Lambda on :9000).
- Run the local Lambda integration test (requires local stack running and `LAMBDA_TOKEN` env): `make test-local`. Optionally set `LAMBDA_URL` to override the invoke URL.

### Required `.env` keys (local/dev)

- `SETLIST_FM_API_KEY`: API key for setlist.fm (fetch recent setlists).
- `SPOTIFY_CLIENT_ID` / `SPOTIFY_CLIENT_SECRET`: Spotify app credentials.
- `SPOTIFY_REDIRECT_URI`: Redirect URI configured for the Spotify app (e.g. `http://localhost:3000`).
- `SPOTIFY_USERNAME`: Target Spotify user for playlist creation.
- `SPOTIFY_REFRESH_TOKEN`: Long-lived refresh token for the above app/user.
- `SETLIST_CACHE`: Path for the setlist cache JSON (relative or absolute).
- `SPOTIFY_TRACK_CACHE`: Path for the Spotify track cache JSON.
- Optional: `SPOTIFY_SCOPES`: Override default scopes (`playlist-modify-public`).
- Optional: `SPOTIFY_CACHE_PATH`: Path for spotipy token cache (defaults to `/tmp/spotify_token_cache`).
- Optional (tests): `LAMBDA_TOKEN` and `LAMBDA_URL` for local integration test.

const form = document.getElementById('playlist-form');
const payloadPreview = document.getElementById('payload-preview');
const responsePreview = document.getElementById('response-preview');
const responseLink = document.getElementById('response-link');
const setlistSummary = document.getElementById('setlist-summary');
const statusText = document.getElementById('status-text');
const statusDot = document.getElementById('status-dot');
const submitButton = document.getElementById('submit-btn');

const bandsInput = document.getElementById('band_names');
const playlistInput = document.getElementById('playlist_name');
const playlistHint = document.getElementById('playlist_hint');
const copyThresholdInput = document.getElementById('copy_last_setlist_threshold');
const maxLengthInput = document.getElementById('max_setlist_length');
const noCacheInput = document.getElementById('no_cache');
const forceSmartInput = document.getElementById('force_smart_setlist');
const fuzzyInput = document.getElementById('use_fuzzy_search');
const rateLimitInput = document.getElementById('rate_limit');
const tokenInput = document.getElementById('token');
const endpointInput = document.getElementById('endpoint');
const fillExampleButton = document.getElementById('fill-example');
const localModeInput = document.getElementById('local_mode');
const TOKEN_STORAGE_KEY = 'ag_bearer_token';
const LOCAL_INVOKE_URL = 'http://127.0.0.1:8787/2015-03-31/functions/function/invocations';
let savedEndpointValue = endpointInput.value;

const parseBands = (value) => value.split(/\r?\n|,/).map((item) => item.trim()).filter(Boolean);

const buildPayload = () => {
  const playlistName = playlistInput.value.trim();
  return {
    band_names: parseBands(bandsInput.value),
    playlist_name: playlistName || null,
    copy_last_setlist_threshold: Number(copyThresholdInput.value) || 15,
    max_setlist_length: Number(maxLengthInput.value) || 12,
    no_cache: Boolean(noCacheInput.checked),
    rate_limit: Number(rateLimitInput.value) || 1.0,
    create_playlist: Boolean(playlistName),
    force_smart_setlist: Boolean(forceSmartInput.checked),
    use_fuzzy_search: Boolean(fuzzyInput.checked),
  };
};

const updatePreview = () => {
  payloadPreview.textContent = JSON.stringify(buildPayload(), null, 2);
};

const updateSubmitLabel = () => {
  const playlistName = playlistInput.value.trim();
  submitButton.textContent = playlistName
    ? 'Create Spotify Playlist'
    : 'Preview setlists + links';
};

const hasToken = () => Boolean(tokenInput.value.trim());
const wantsPlaylistCreation = () => Boolean(playlistInput.value.trim());

const updatePlaylistNameState = () => {
  const tokenPresent = hasToken();
  const creationEnabled = wantsPlaylistCreation();
  playlistInput.disabled = !tokenPresent;
  playlistInput.required = creationEnabled && tokenPresent;
  playlistHint.textContent = tokenPresent
    ? creationEnabled
      ? 'Playlist will be created'
      : 'Leave empty to preview only'
    : 'Add a bearer token to enable playlist creation';
};

const setStatus = (text, color = 'var(--accent)') => {
  statusText.textContent = text;
  statusDot.style.background = color;
  statusDot.style.boxShadow = `0 0 0 4px ${color === 'var(--accent)' ? 'rgba(124, 246, 210, 0.12)' : 'rgba(255, 124, 124, 0.12)'}`;
};

const updateResponseLink = (maybeUrl, created) => {
  if (created && maybeUrl) {
    responseLink.innerHTML = `<a href="${maybeUrl}" target="_blank" rel="noopener noreferrer">Open playlist ↗</a>`;
  } else if (!created) {
    responseLink.innerHTML = '<div class="chip-row"><span class="tag estimated">Preview mode</span><span>No playlist created (follow links below)</span></div>';
  } else {
    responseLink.textContent = '';
  }
};

const renderSetlistSummary = (inner) => {
  const setlists = inner?.setlists || [];
  if (!Array.isArray(setlists) || setlists.length === 0) {
    return '';
  }

  return `<div class="setlist-grid">
    ${setlists.map((setlist) => {
      const missing = setlist.missing_songs || [];
      const songs = setlist.songs || [];
      const tagClass = setlist.setlist_type === 'fresh' ? 'fresh' : 'estimated';
      const songList = songs.map((song) => {
        const link = song.spotify_url
          ? `<a href="${song.spotify_url}" target="_blank" rel="noopener noreferrer">Spotify ↗</a>`
          : '<span class="missing">Not found</span>';
        return `<div class="song-row">
          <span>${song.name}</span>
          ${link}
        </div>`;
      }).join('');
      const chips = [];
      if (setlist.setlist_date) chips.push(`Date ${setlist.setlist_date}`);
      if (setlist.last_setlist_age_days !== null && setlist.last_setlist_age_days !== undefined) {
        chips.push(`${setlist.last_setlist_age_days} days old`);
      }
      if (missing.length > 0) {
        chips.push(`<strong>${missing.length} missing</strong>`);
      }
      return `<div class="setlist-card">
        <div class="setlist-header">
          <h4>${setlist.band}</h4>
          <span class="tag ${tagClass}">${setlist.setlist_type}</span>
        </div>
        ${songList}
        <div class="chip-row">${chips.join(' · ')}</div>
      </div>`;
    }).join('')}
  </div>`;
};

const buildRequest = (endpoint, payload, authHeader) => {
  const autoDetectLocal = endpoint.includes('/2015-03-31/functions/function/invocations');
  const isLocalInvoke = localModeInput.checked || autoDetectLocal;

  if (isLocalInvoke) {
    // Local Lambda runtime expects the full event envelope.
    return {
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        headers: authHeader ? { authorization: authHeader } : {},
        body: JSON.stringify(payload),
        isBase64Encoded: false,
      }),
    };
  }

  // Deployed Lambda/function URL/API Gateway expects the raw payload and auth header directly.
  const headers = { 'Content-Type': 'application/json' };
  if (authHeader) {
    headers['Authorization'] = authHeader;
  }

  return { headers, body: JSON.stringify(payload) };
};

form.addEventListener('input', () => {
  updatePreview();
  updateSubmitLabel();
  updatePlaylistNameState();
});

localModeInput.addEventListener('change', () => {
  if (localModeInput.checked) {
    savedEndpointValue = endpointInput.value;
    endpointInput.value = LOCAL_INVOKE_URL;
    setStatus('Local mode enabled (endpoint overridden and request wrapped)');
  } else {
    endpointInput.value = savedEndpointValue || endpointInput.value;
    setStatus('Local mode off');
  }
});

const applyTokenFromQuery = () => {
  const url = new URL(window.location.href);
  const queryToken = url.searchParams.get('token') || url.searchParams.get('bearer');
  const storedToken = localStorage.getItem(TOKEN_STORAGE_KEY);

  if (queryToken) {
    tokenInput.value = queryToken;
    localStorage.setItem(TOKEN_STORAGE_KEY, queryToken);

    url.searchParams.delete('token');
    url.searchParams.delete('bearer');
    const cleanSearch = url.searchParams.toString();
    const newUrl = cleanSearch ? `${url.pathname}?${cleanSearch}${url.hash}` : `${url.pathname}${url.hash}`;
    history.replaceState(null, '', newUrl);
    setStatus('Token captured from link and hidden from URL');
  } else if (storedToken) {
    tokenInput.value = storedToken;
  }
  updatePlaylistNameState();
};

tokenInput.addEventListener('input', () => {
  const token = tokenInput.value.trim();
  if (token) {
    localStorage.setItem(TOKEN_STORAGE_KEY, token);
  }
  updatePlaylistNameState();
});

if (fillExampleButton) {
  fillExampleButton.addEventListener('click', () => {
    bandsInput.value = 'Band A\nBand B\nArtist C';
    playlistInput.value = 'Rehearsal Mix';
    copyThresholdInput.value = 10;
    maxLengthInput.value = 12;
    rateLimitInput.value = 0.5;
    noCacheInput.checked = true;
    updatePreview();
    updateSubmitLabel();
    setStatus('Example payload loaded');
  });
}

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  const payload = buildPayload();
  if (payload.band_names.length === 0) {
    setStatus('At least one band is required.', 'salmon');
    return;
  }

  const endpoint = endpointInput.value.trim();
  if (!endpoint) {
    setStatus('Endpoint URL is required.', 'salmon');
    return;
  }

  setStatus('Sending request...');
  responsePreview.textContent = 'Waiting for response...';
  setlistSummary.innerHTML = '<div class="chip-row"><span>Working...</span></div>';
  submitButton.disabled = true;
  const originalLabel = submitButton.textContent;
  submitButton.textContent = 'Working...';

  const token = tokenInput.value.trim();
  const wantsCreation = Boolean(payload.playlist_name);
  if (wantsCreation && !token) {
    setStatus('Add a bearer token to create the playlist, or clear the playlist name to preview.', '#ff7c7c');
    submitButton.disabled = false;
    submitButton.textContent = originalLabel;
    return;
  }
  const authHeader = token ? (token.startsWith('Bearer ') ? token : `Bearer ${token}`) : '';
  const { headers, body } = buildRequest(endpoint, payload, authHeader);

  try {
    const response = await fetch(endpoint, {
      method: 'POST',
      headers,
      body,
    });

    const text = await response.text();
    let parsedBody;
    try {
      parsedBody = text ? JSON.parse(text) : null;
    } catch (err) {
      parsedBody = text;
    }

    let innerBody = parsedBody;
    if (parsedBody && typeof parsedBody === 'object' && typeof parsedBody.body === 'string') {
      try {
        innerBody = JSON.parse(parsedBody.body);
      } catch (_) {
        innerBody = parsedBody.body;
      }
    }

    const output = {
      status: response.status,
      ok: response.ok,
      body: parsedBody,
      inner: innerBody,
    };

    responsePreview.textContent = JSON.stringify(output, null, 2);
    const linkUrl = innerBody?.playlist?.url || parsedBody?.playlist?.url;
    const created = Boolean(innerBody?.created_playlist ?? parsedBody?.created_playlist);
    updateResponseLink(linkUrl, created);
    const summary = renderSetlistSummary(innerBody || parsedBody);
    setlistSummary.innerHTML = summary || '<div class="chip-row"><span>No results yet.</span></div>';
    setStatus(response.ok ? 'Lambda responded successfully' : 'Lambda returned an error', response.ok ? 'var(--accent)' : '#ff7c7c');
  } catch (error) {
    responsePreview.textContent = `Request failed: ${error.message}`;
    updateResponseLink(null, false);
    setlistSummary.innerHTML = '';
    setStatus('Network error', '#ff7c7c');
  } finally {
    submitButton.disabled = false;
    submitButton.textContent = originalLabel;
  }
});

// Initialize preview on load.
updatePlaylistNameState();
updatePreview();
applyTokenFromQuery();
updateSubmitLabel();

// Auto-enable local mode when served from localhost to streamline `make run`.
const isLocalHost = ['localhost', '127.0.0.1'].includes(window.location.hostname);
if (isLocalHost && !localModeInput.checked) {
  localModeInput.checked = true;
  localModeInput.dispatchEvent(new Event('change'));
}

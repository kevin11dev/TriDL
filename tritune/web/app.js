'use strict';
/* TriTune web UI — vanilla JS, no build step. */

// ── tiny helpers ─────────────────────────────────────────────────────────
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const enc = encodeURIComponent;
const fmt = s => { s = Math.max(0, Math.floor(s || 0)); const h = Math.floor(s / 3600), m = Math.floor(s % 3600 / 60); return (h ? h + ':' + String(m).padStart(2, '0') : m) + ':' + String(s % 60).padStart(2, '0'); };
const big = u => (u || '').replace(/=w\d+-h\d+/, '=w544-h544').replace(/-(large|t\d+x\d+)\.jpg/, '-t500x500.jpg');

const st = d => `<path d="${d}" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>`;
const ICON = {
  play: '<path d="M7 4.5v15a1 1 0 0 0 1.5.86l13-7.5a1 1 0 0 0 0-1.72l-13-7.5A1 1 0 0 0 7 4.5z"/>',
  pause: '<path d="M6 4h4.5v16H6zM13.500 4H18v16h-4.500z"/>',
  next: '<path d="M5 4.6v14.800a.8.8 0 0 0 1.200.700L17 13.600V19a1 1 0 0 0 2 0V5a1 1 0 0 0-2 0v5.400L6.200 3.900A.8.8 0 0 0 5 4.600z"/>',
  prev: '<path d="M19 4.6v14.800a.8.8 0 0 1-1.200.700L7 13.600V19a1 1 0 0 1-2 0V5a1 1 0 0 1 2 0v5.400l10.800-6.500a.8.8 0 0 1 1.200.700z"/>',
  shuffle: st('M3 7h3c5 0 6 10 11 10h4m0 0-3-3m3 3-3 3M3 17h3c1.700 0 2.900-1.100 4-2.600M21 7h-4c-1.700 0-2.900 1.100-4 2.600M21 7l-3-3m3 3-3 3'),
  repeat: st('M17 2l4 4-4 4M3 11V9a3 3 0 0 1 3-3h15M7 22l-4-4 4-4m14-1v2a3 3 0 0 1-3 3H3'),
  repeat1: st('M17 2l4 4-4 4M3 11V9a3 3 0 0 1 3-3h15M7 22l-4-4 4-4m14-1v2a3 3 0 0 1-3 3H3M11 10.500l1.500-1v5'),
  heart: st('M12 20.500s-8-4.700-8-10.500a4.500 4.500 0 0 1 8-2.800A4.500 4.500 0 0 1 20 10c0 5.800-8 10.500-8 10.500z'),
  heartOn: '<path d="M12 21s-9-5.200-9-11.200A5.200 5.200 0 0 1 12 6.500a5.200 5.200 0 0 1 9 3.300C21 15.800 12 21 12 21z"/>',
  home: '<path d="M12.700 2.300a1 1 0 0 0-1.400 0l-8 7.500a1 1 0 0 0-.300.700V20a1 1 0 0 0 1 1h5v-6h6v6h5a1 1 0 0 0 1-1v-9.500a1 1 0 0 0-.300-.700z"/>',
  search: st('M10.500 18a7.500 7.500 0 1 1 0-15 7.500 7.500 0 0 1 0 15zM16 16l5 5'),
  library: st('M4 3v18M9 3v18M14 4.500l5.500 15.500'),
  plus: st('M12 5v14M5 12h14'),
  down: st('M12 4v11m0 0-4.500-4.500M12 15l4.500-4.500M5 20h14'),
  close: st('M6 6l12 12M18 6L6 18'),
  queue: st('M4 6h16M4 11h16M4 16h9m4-1v6l5-3z'),
  vol: st('M4 9.500v5h3.500L12 19V5L7.500 9.500zM15.500 9a4 4 0 0 1 0 6M18 6.500a8 8 0 0 1 0 11'),
  mute: st('M4 9.500v5h3.500L12 19V5L7.500 9.500zM16 9.500l5 5m0-5-5 5'),
  dots: '<circle cx="5" cy="12" r="1.800"/><circle cx="12" cy="12" r="1.800"/><circle cx="19" cy="12" r="1.800"/>',
  back: st('M15 5l-7 7 7 7'), fwd: st('M9 5l7 7-7 7'),
  clock: st('M12 21a9 9 0 1 1 0-18 9 9 0 0 1 0 18zM12 7v5l3 2'),
  note: st('M9 18V5l11-2v13M9 18a3 3 0 1 1-6 0 3 3 0 0 1 6 0zm11-2a3 3 0 1 1-6 0 3 3 0 0 1 6 0z'),
  spin: st('M12 3a9 9 0 1 0 9 9'),
  radio: st('M12 12v.01M8.500 8.500a5 5 0 0 0 0 7m7 0a5 5 0 0 0 0-7M5.600 5.600a9 9 0 0 0 0 12.800m12.800 0a9 9 0 0 0 0-12.800'),
};
const svg = n => `<svg viewBox="0 0 24 24">${ICON[n]}</svg>`;

async function api(path, opts = {}) {
  if (opts.body && typeof opts.body !== 'string') { opts.body = JSON.stringify(opts.body); opts.headers = { 'Content-Type': 'application/json' }; }
  const r = await fetch('/api/' + path, opts);
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.error || `Request failed (${r.status})`);
  return data;
}
function toast(msg, err) {
  const el = document.createElement('div');
  el.className = 'toast' + (err ? ' err' : ''); el.textContent = msg;
  $('#toasts').append(el); setTimeout(() => el.remove(), err ? 5000 : 2500);
}
const fail = e => toast(e.message || String(e), true);

// ── state ────────────────────────────────────────────────────────────────
const S = { queue: [], idx: -1, shuffle: false, repeat: 'off', autoplay: true, liked: new Set(), playlists: [] };
// Playback happens natively in mpv (see player.py). This object mirrors the
// small part of the HTMLAudioElement interface the UI uses, over a WebSocket.
const audio = (() => {
  const L = {}, st = { tid: null, paused: true, time: 0, duration: 0, loading: false, volume: .8, muted: false };
  let ws, backlog = [], error = '';
  const emit = n => (L[n] || []).forEach(f => f());
  const send = o => { if (ws && ws.readyState === 1) ws.send(JSON.stringify(o)); else backlog.push(o); };
  function onMessage(m) {
    if (m.ev === 'state') {
      if (!m.tid || (st.tid && m.tid !== st.tid)) return;   // nothing loaded, or a stale track
      const was = { ...st };
      Object.assign(st, { tid: m.tid, paused: m.paused, time: m.time, loading: m.loading, duration: m.duration || st.duration });
      if (st.duration !== was.duration) emit('loadedmetadata');
      if (st.loading !== was.loading) emit(st.loading ? 'waiting' : 'canplay');
      if (st.paused !== was.paused) emit(st.paused ? 'pause' : 'play');
      if (!st.loading && !st.paused && (was.loading || was.paused)) emit('playing');
      emit('timeupdate');
    } else if (m.tid === st.tid && (m.ev === 'ended' || m.ev === 'error')) {
      Object.assign(st, { tid: null, paused: true, loading: false });
      error = m.msg || '';
      emit(m.ev);
    }
  }
  (function connect() {
    ws = new WebSocket(`ws://${location.host}/api/player`);
    ws.onopen = () => { send({ cmd: 'volume', value: st.volume }); send({ cmd: 'mute', value: st.muted }); backlog.splice(0).forEach(send); };
    ws.onmessage = e => onMessage(JSON.parse(e.data));
    ws.onclose = () => setTimeout(connect, 1000);
  })();
  return {
    addEventListener(n, f) { (L[n] ||= []).push(f); },
    load(track, at = 0, play = true) {
      Object.assign(st, { tid: track.id, paused: !play, time: at, duration: track.duration || 0, loading: true });
      send({ cmd: 'load', track, at, play });
    },
    play() { if (st.tid) { st.paused = false; send({ cmd: 'pause', value: false }); emit('play'); } },
    pause() { if (st.tid) { st.paused = true; send({ cmd: 'pause', value: true }); emit('pause'); } },
    get src() { return st.tid || ''; },          // id of the track mpv has loaded
    get error() { return error; },
    get paused() { return st.paused; },
    get duration() { return st.duration; },
    get currentTime() { return st.time; },
    set currentTime(v) { if (st.tid) { st.time = v; send({ cmd: 'seek', time: v }); emit('timeupdate'); } },
    get volume() { return st.volume; },
    set volume(v) { st.volume = v; send({ cmd: 'volume', value: v }); },
    get muted() { return st.muted; },
    set muted(v) { st.muted = v; send({ cmd: 'mute', value: v }); },
  };
})();
let lists = [];           // track lists rendered in the current view
let renderToken = 0;
const cur = () => S.queue[S.idx];

function saveState() {
  try {
    localStorage.setItem('tritune', JSON.stringify({
      queue: S.queue.slice(0, 500), idx: S.idx, shuffle: S.shuffle, repeat: S.repeat, autoplay: S.autoplay,
      vol: audio.volume, muted: audio.muted, time: audio.currentTime || 0,
    }));
  } catch { }
}
function loadState() {
  try {
    const d = JSON.parse(localStorage.getItem('tritune') || '{}');
    if (Array.isArray(d.queue)) { S.queue = d.queue; S.idx = Math.min(d.idx ?? -1, d.queue.length - 1); }
    S.shuffle = !!d.shuffle; S.repeat = d.repeat || 'off'; S.autoplay = d.autoplay !== false;
    audio.volume = d.vol ?? 0.8; audio.muted = !!d.muted;
    return d.time || 0;
  } catch { return 0; }
}

// ── player ───────────────────────────────────────────────────────────────
let errors = 0, seeking = false, resumeAt = 0;
const prefetched = new Set();

function loadTrack(play = true, at = 0) {
  const t = cur();
  if (!t) return;
  resumeAt = 0;
  audio.load(t, at, play);
  if (play) setLoading(true);
  updateNow();
  if (play) api('history', { method: 'POST', body: t }).catch(() => { });
  if (S.autoplay && S.repeat === 'off' && S.idx >= S.queue.length - 1) extendRadio(t);
  saveState();
}
function playAt(i) { if (i >= 0 && i < S.queue.length) { S.idx = i; loadTrack(true); } }
function playList(tracks, i = 0) {
  if (!tracks.length) return;
  if (S.shuffle) {
    const rest = tracks.filter((_, k) => k !== i);
    for (let k = rest.length - 1; k > 0; k--) { const j = Math.floor(Math.random() * (k + 1)); [rest[k], rest[j]] = [rest[j], rest[k]]; }
    S.queue = [tracks[i], ...rest]; S.idx = 0;
  } else { S.queue = tracks.slice(); S.idx = i; }
  loadTrack(true);
}
function toggle() {
  if (!cur()) return;
  if (audio.src !== cur().id) return loadTrack(true, resumeAt);
  audio.paused ? audio.play() : audio.pause();
}
function next(auto) {
  if (auto && S.repeat === 'one') { loadTrack(true); return; }
  if (S.idx + 1 < S.queue.length) playAt(S.idx + 1);
  else if (S.repeat !== 'off' && S.queue.length) playAt(0);
  else if (auto) { setLoading(false); updatePlayBtn(); }
}
function prev() {
  if (audio.currentTime > 3 || S.idx <= 0) { audio.currentTime = 0; return; }
  playAt(S.idx - 1);
}
function enqueue(tracks, nextUp) {
  const had = S.queue.length;
  if (nextUp) S.queue.splice(S.idx + 1, 0, ...tracks); else S.queue.push(...tracks);
  if (!had) { S.idx = 0; loadTrack(false); }
  renderQueue(); saveState();
  toast(nextUp ? 'Playing next' : 'Added to queue');
}
let radioBusy = false;
async function extendRadio(t) {
  if (radioBusy) return;
  radioBusy = true;
  try {
    const have = new Set(S.queue.map(x => x.id));
    const more = (await api('radio', { method: 'POST', body: t })).items.filter(x => !have.has(x.id));
    if (more.length && cur() && cur().id === t.id) { S.queue.push(...more.slice(0, 20)); renderQueue(); saveState(); }
  } catch { } finally { radioBusy = false; }
}
function prefetchNext() {
  const n = S.queue[S.idx + 1];
  if (n && !prefetched.has(n.id)) { prefetched.add(n.id); fetch('/api/prefetch/' + enc(n.id)).catch(() => { }); }
}

function setLoading(on) { $('#play').classList.toggle('loading', on); updatePlayBtn(); }
function updatePlayBtn() {
  const b = $('#play'), loading = b.classList.contains('loading');
  b.innerHTML = svg(loading ? 'spin' : audio.paused ? 'play' : 'pause');
  b.title = audio.paused ? 'Play' : 'Pause';
  $$('.big-play').forEach(el => {
    const mine = cur() && mainList().some(t => t.id === cur().id);
    el.innerHTML = svg(mine && !audio.paused ? 'pause' : 'play');
  });
}
function likeIcon(id) { return svg(S.liked.has(id) ? 'heartOn' : 'heart'); }
function updateNow() {
  const t = cur();
  $('#np-art').hidden = $('#np-like').hidden = !t;
  $('#np-title').textContent = t ? t.title : '';
  $('#np-artist').textContent = t ? t.artist : '';
  if (t) {
    $('#np-art').src = t.thumb || 'icon.svg';
    $('#np-artist').href = t.artist_id ? '#/artist/' + enc(t.artist_id) : '#/search/' + enc(t.artist);
    $('#np-title').href = t.album_id ? '#/album/' + enc(t.album_id) : '#/search/' + enc(t.title);
    $('#np-like').innerHTML = likeIcon(t.id); $('#np-like').classList.toggle('on', S.liked.has(t.id));
    $('#dur').textContent = fmt(t.duration);
    document.title = `${t.title} • ${t.artist}`;
  }
  $$('.row.playing, .qrow.playing').forEach(r => r.classList.remove('playing'));
  if (t) $$(`.row[data-tid="${CSS.escape(t.id)}"]`).forEach(r => r.classList.add('playing'));
  renderQueue(); updatePlayBtn();
}
function setSlider(el, frac) { el.style.setProperty('--p', (Math.min(1, Math.max(0, frac)) * 100) + '%'); }
function duration() { return isFinite(audio.duration) && audio.duration > 0 ? audio.duration : (cur()?.duration || 0); }

audio.addEventListener('loadedmetadata', () => { $('#dur').textContent = fmt(duration()); });
audio.addEventListener('playing', () => { errors = 0; setLoading(false); prefetchNext(); });
audio.addEventListener('waiting', () => setLoading(true));
audio.addEventListener('canplay', () => setLoading(false));
audio.addEventListener('play', updatePlayBtn);
audio.addEventListener('pause', updatePlayBtn);
audio.addEventListener('ended', () => next(true));
audio.addEventListener('error', () => {
  setLoading(false);
  const t = cur();
  toast(`Can't play "${t ? t.title : 'track'}"` + (audio.error ? ': ' + audio.error.slice(0, 300) : ''), true);
  if (++errors < 3 && S.idx + 1 < S.queue.length) next(); else errors = 0;
});
let lastSave = 0;
audio.addEventListener('timeupdate', () => {
  if (seeking) return;
  const d = duration(), c = audio.currentTime;
  $('#cur').textContent = fmt(c);
  $('#seek').value = d ? c / d * 1000 : 0; setSlider($('#seek'), d ? c / d : 0);
  if (Date.now() - lastSave > 5000) { lastSave = Date.now(); saveState(); }
});
$('#seek').addEventListener('input', e => { seeking = true; setSlider(e.target, e.target.value / 1000); $('#cur').textContent = fmt(e.target.value / 1000 * duration()); });
$('#seek').addEventListener('change', e => {
  seeking = false;
  const at = e.target.value / 1000 * duration();
  if (audio.src === cur()?.id) audio.currentTime = at; else resumeAt = at;
});
function updateVol() {
  const v = audio.muted ? 0 : audio.volume;
  $('#vol').value = v * 100; setSlider($('#vol'), v);
  $('#mute').innerHTML = svg(v === 0 ? 'mute' : 'vol');
}
$('#vol').addEventListener('input', e => { audio.muted = false; audio.volume = e.target.value / 100; updateVol(); saveState(); });
$('#mute').onclick = () => { audio.muted = !audio.muted; updateVol(); saveState(); };
function updateModes() {
  $('#shuffle').classList.toggle('on', S.shuffle);
  $('#repeat').classList.toggle('on', S.repeat !== 'off');
  $('#repeat').innerHTML = svg(S.repeat === 'one' ? 'repeat1' : 'repeat');
  $('#autoplay').classList.toggle('on', S.autoplay);
}
$('#play').onclick = toggle;
$('#next').onclick = () => next(false);
$('#prev').onclick = prev;
$('#shuffle').onclick = () => {
  S.shuffle = !S.shuffle;
  if (S.shuffle) {  // shuffle what is still to come
    const rest = S.queue.splice(S.idx + 1);
    for (let k = rest.length - 1; k > 0; k--) { const j = Math.floor(Math.random() * (k + 1)); [rest[k], rest[j]] = [rest[j], rest[k]]; }
    S.queue.push(...rest); renderQueue();
  }
  updateModes(); saveState();
};
$('#repeat').onclick = () => { S.repeat = { off: 'all', all: 'one', one: 'off' }[S.repeat]; updateModes(); saveState(); };
$('#autoplay').onclick = () => { S.autoplay = !S.autoplay; updateModes(); saveState(); toast('Autoplay ' + (S.autoplay ? 'on' : 'off')); };
$('#np-like').onclick = () => cur() && toggleLike(cur());
// ── queue panel ──────────────────────────────────────────────────────────
function qrow(t, i) {
  return `<div class="qrow${i === S.idx ? ' playing' : ''}" data-q="${i}"><img loading="lazy" src="${esc(t.thumb || 'icon.svg')}" alt="">
    <div><b>${esc(t.title)}</b><span>${esc(t.artist)}</span></div>
    ${i === S.idx ? '' : `<button class="icon-btn" data-qdel="${i}" title="Remove">${svg('close')}</button>`}</div>`;
}
function renderQueue() {
  if ($('#queue').hidden) return;
  const up = S.queue.slice(S.idx + 1, S.idx + 101);
  $('#queue-list').innerHTML = cur()
    ? `<h4>Now playing</h4>${qrow(cur(), S.idx)}` + (up.length ? `<h4>Next up</h4>${up.map((t, k) => qrow(t, S.idx + 1 + k)).join('')}` : '')
    : '<div class="empty">Your queue is empty</div>';
}
$('#queue-list').onclick = e => {
  const del = e.target.closest('[data-qdel]');
  if (del) { S.queue.splice(+del.dataset.qdel, 1); renderQueue(); saveState(); return; }
  const row = e.target.closest('[data-q]');
  if (row) playAt(+row.dataset.q);
};
function toggleQueue() {
  const q = $('#queue'); q.hidden = !q.hidden; $('#queue-btn').classList.toggle('on', !q.hidden); renderQueue();
}
$('#queue-btn').onclick = toggleQueue; $('#queue-close').onclick = toggleQueue;

// ── library ──────────────────────────────────────────────────────────────
async function refreshLibrary() {
  const d = await api('library');
  S.playlists = d.playlists; S.liked = new Set(d.liked);
  renderSidebar();
}
function renderSidebar() {
  const h = location.hash;
  const item = (href, art, title, sub) => `<a class="lib-item${h === href ? ' active' : ''}" href="${href}" title="${esc(title)}">${art}<div class="t"><b>${esc(title)}</b><span>${esc(sub)}</span></div></a>`;
  $('#lib').innerHTML = item('#/liked', `<div class="ph liked">${svg('heartOn')}</div>`, 'Liked Songs', `Playlist • ${S.liked.size} song${S.liked.size === 1 ? '' : 's'}`)
    + S.playlists.map(p => item('#/playlist/' + p.id, p.thumb ? `<img loading="lazy" src="${esc(p.thumb)}" alt="">` : `<div class="ph">${svg('note')}</div>`, p.name, `Playlist • ${p.count} song${p.count === 1 ? '' : 's'}`)).join('')
    + item('#/history', `<div class="ph">${svg('clock')}</div>`, 'Recently played', 'History');
}
async function toggleLike(t) {
  const on = !S.liked.has(t.id);
  try {
    if (on) { await api('likes', { method: 'POST', body: t }); S.liked.add(t.id); toast('Added to Liked Songs'); }
    else { await api('likes/' + enc(t.id), { method: 'DELETE' }); S.liked.delete(t.id); toast('Removed from Liked Songs'); }
  } catch (e) { return fail(e); }
  $$(`.row[data-tid="${CSS.escape(t.id)}"] [data-act="like"]`).forEach(b => { b.innerHTML = likeIcon(t.id); b.classList.toggle('on', on); });
  if (cur() && cur().id === t.id) { $('#np-like').innerHTML = likeIcon(t.id); $('#np-like').classList.toggle('on', on); }
  renderSidebar();
  if (location.hash === '#/liked' && !on) render();
}
async function addToPlaylist(pid, tracks) {
  try {
    const r = await api(`playlists/${pid}/tracks`, { method: 'POST', body: { tracks } });
    toast(r.added ? `Added to ${S.playlists.find(p => p.id === pid)?.name || 'playlist'}` : 'Already in playlist');
    await refreshLibrary();
  } catch (e) { fail(e); }
}
async function newPlaylist(tracks = []) {
  const name = await ask({ title: 'Create playlist', placeholder: 'Playlist name', value: `My Playlist #${S.playlists.length + 1}`, ok: 'Create' });
  if (!name) return;
  try {
    const r = await api('playlists', { method: 'POST', body: { name, tracks } });
    await refreshLibrary();
    if (!tracks.length) location.hash = '#/playlist/' + r.id; else toast(`Added to ${name}`);
  } catch (e) { fail(e); }
}
$('#new-pl').onclick = () => newPlaylist();
$('#import').onclick = async () => {
  const url = await ask({
    title: 'Import playlist', ok: 'Import', placeholder: 'https://open.spotify.com/playlist/…',
    text: 'Paste a public Spotify, YouTube Music or SoundCloud playlist / album link. Spotify tracks are matched to the same songs on YouTube Music (first 100 tracks).',
  });
  if (!url) return;
  toast('Importing… this can take a few seconds');
  try {
    const r = await api('import', { method: 'POST', body: { url } });
    await refreshLibrary();
    toast(`Imported ${r.count} songs` + (r.missing ? ` (${r.missing} not found)` : ''));
    location.hash = '#/playlist/' + r.id;
  } catch (e) { fail(e); }
};

// ── modal + context menu ─────────────────────────────────────────────────
function ask({ title, text = '', value = '', placeholder = '', ok = 'OK', input = true, danger = false }) {
  return new Promise(res => {
    const m = $('#modal'), inp = $('#modal-input');
    $('#modal-title').textContent = title; $('#modal-text').textContent = text; $('#modal-text').hidden = !text;
    inp.hidden = !input; inp.value = value; inp.placeholder = placeholder;
    $('#modal-ok').textContent = ok; $('#modal-ok').classList.toggle('danger', danger);
    m.hidden = false; if (input) { inp.focus(); inp.select(); } else $('#modal-ok').focus();
    const done = v => { m.hidden = true; $('#modal-box').onsubmit = $('#modal-cancel').onclick = m.onmousedown = null; res(v); };
    $('#modal-box').onsubmit = e => { e.preventDefault(); done(input ? inp.value.trim() || null : true); };
    $('#modal-cancel').onclick = () => done(null);
    m.onmousedown = e => { if (e.target === m) done(null); };
  });
}
function showMenu(x, y, items) {
  const m = $('#menu');
  m.innerHTML = items.map((it, i) => it === '-' ? '<hr>' : it.head ? `<small>${esc(it.head)}</small>` : `<button data-m="${i}">${esc(it.label)}</button>`).join('');
  m.hidden = false;
  const r = m.getBoundingClientRect();
  m.style.left = Math.max(4, Math.min(x, innerWidth - r.width - 8)) + 'px';
  m.style.top = Math.max(4, Math.min(y, innerHeight - r.height - 8)) + 'px';
  m.onclick = e => { const b = e.target.closest('[data-m]'); if (b) { hideMenu(); items[+b.dataset.m].fn(); } };
}
function hideMenu() { $('#menu').hidden = true; $$('.row.ctx').forEach(r => r.classList.remove('ctx')); }
document.addEventListener('mousedown', e => { if (!e.target.closest('#menu')) hideMenu(); });
window.addEventListener('blur', hideMenu);

function trackMenu(t, x, y, row) {
  const pid = route().name === 'playlist' ? +route().arg : null;
  const items = [
    { label: 'Play next', fn: () => enqueue([t], true) },
    { label: 'Add to queue', fn: () => enqueue([t]) },
    { label: 'Go to song radio', fn: () => { location.hash = '#/radio/' + enc(t.id); sessionStorage.setItem('radio:' + t.id, JSON.stringify(t)); } },
    '-',
    { label: S.liked.has(t.id) ? 'Remove from Liked Songs' : 'Save to Liked Songs', fn: () => toggleLike(t) },
  ];
  if (pid) items.push({ label: 'Remove from this playlist', fn: async () => { try { await api(`playlists/${pid}/tracks/${enc(t.id)}`, { method: 'DELETE' }); await refreshLibrary(); render(); } catch (e) { fail(e); } } });
  if (t.artist_id) items.push({ label: 'Go to artist', fn: () => { location.hash = '#/artist/' + enc(t.artist_id); } });
  if (t.album_id) items.push({ label: 'Go to album', fn: () => { location.hash = '#/album/' + enc(t.album_id); } });
  if (t.url) items.push({ label: 'Copy song link', fn: () => navigator.clipboard?.writeText(t.url).then(() => toast('Link copied'), () => { }) });
  items.push('-', { head: 'Add to playlist' }, { label: '+ New playlist', fn: () => newPlaylist([t]) },
    ...S.playlists.filter(p => p.id !== pid).map(p => ({ label: p.name, fn: () => addToPlaylist(p.id, [t]) })));
  if (row) row.classList.add('ctx');
  showMenu(x, y, items);
}

// ── view building blocks ─────────────────────────────────────────────────
// The track list a view's big play button controls (its first table).
function mainList() { const r = $('.row[data-l]', main); return (r && lists[r.dataset.l]) || []; }
function addList(tracks) { lists.push(tracks); return lists.length - 1; }
function trackTable(tracks, { head = true, limit = 0 } = {}) {
  const l = addList(tracks), c = cur();
  const rows = (limit ? tracks.slice(0, limit) : tracks).map((t, i) => `
    <div class="row${c && c.id === t.id ? ' playing' : ''}" data-l="${l}" data-i="${i}" data-tid="${esc(t.id)}">
      <div class="num"><span>${i + 1}</span><button data-act="play" title="Play">${svg('play')}</button></div>
      <div class="main"><img loading="lazy" src="${esc(t.thumb || 'icon.svg')}" alt="">
        <div class="tt"><b>${esc(t.title)}</b><span><i class="src ${t.source}">${t.source === 'sc' ? 'SC' : 'YT'}</i>${esc(t.artist)}</span></div></div>
      ${t.album_id ? `<a class="alb" href="#/album/${enc(t.album_id)}">${esc(t.album)}</a>` : `<span class="alb">${esc(t.album || '')}</span>`}
      <button class="icon-btn${S.liked.has(t.id) ? ' on' : ''}" data-act="like" title="Like">${likeIcon(t.id)}</button>
      <div class="dur">${t.duration ? fmt(t.duration) : ''}</div>
      <button class="icon-btn" data-act="more" title="More">${svg('dots')}</button>
    </div>`).join('');
  return `<div class="tracks">${head ? `<div class="thead"><span>#</span><span>Title</span><span>Album</span><span>${svg('clock')}</span></div>` : ''}${rows}</div>`;
}
const cover = (src, icon = 'note') => src ? `<img loading="lazy" src="${esc(src)}" alt="">` : `<div class="ph">${svg(icon)}</div>`;
function card(href, thumb, title, sub, cls = '') {
  return `<a class="card ${cls}" href="${href}"><div class="art">${cover(thumb)}</div><b>${esc(title)}</b><span>${esc(sub)}</span></a>`;
}
function trackCards(tracks) {
  const l = addList(tracks);
  return `<div class="cards scroll">${tracks.map((t, i) => `<div class="card" data-act="play" data-l="${l}" data-i="${i}">
    <div class="art">${cover(t.thumb)}<span class="fab">${svg('play')}</span></div><b>${esc(t.title)}</b><span>${esc(t.artist)}</span></div>`).join('')}</div>`;
}
function hero({ kind, title, info, thumb, tint, cls = '', ph }) {
  return `<div class="hero ${cls}" style="--tint:${tint}">${ph || cover(big(thumb))}
    <div class="meta"><div class="kind">${kind}</div><h1>${esc(title)}</h1><div class="info">${info}</div></div></div>`;
}
function total(tracks) {
  const s = tracks.reduce((a, t) => a + (t.duration || 0), 0), h = Math.floor(s / 3600), m = Math.round(s % 3600 / 60);
  return `${tracks.length} song${tracks.length === 1 ? '' : 's'}` + (s ? `, ${h ? h + ' hr ' : ''}${m} min` : '');
}
const skeleton = n => Array(n).fill('<div class="skeleton"></div>').join('');
const empty = (title, text) => `<div class="empty"><b>${esc(title)}</b>${esc(text)}</div>`;

// ── views ────────────────────────────────────────────────────────────────
const main = $('#main');
function route() {
  const [name = 'home', arg = '', extra = ''] = location.hash.replace(/^#\/?/, '').split('/');
  return { name: name || 'home', arg: decodeURIComponent(arg), extra: decodeURIComponent(extra) };
}
const VIEWS = {
  async home(_, set) {
    const hr = new Date().getHours();
    const tiles = [`<a class="tile" href="#/liked"><div class="ph liked">${svg('heartOn')}</div><span>Liked Songs</span></a>`,
    ...S.playlists.slice(0, 7).map(p => `<a class="tile" href="#/playlist/${p.id}">${cover(p.thumb)}<span>${esc(p.name)}</span></a>`)];
    const top = `<h1 class="greeting">Good ${hr < 5 ? 'evening' : hr < 12 ? 'morning' : hr < 18 ? 'afternoon' : 'evening'}</h1><div class="tiles">${tiles.join('')}</div>`;
    set(top + skeleton(4));
    const recent = (await api('history')).items;
    if (!recent.length) return set(top + empty('Welcome to TriTune', 'Search for a song, artist or album to start listening — or import a playlist from the library panel.'));
    const base = top + `<h2>Recently played</h2>${trackCards(recent.slice(0, 20))}`;
    set(base + `<h2>Recommended for you</h2>${skeleton(4)}`);
    const keep = lists.slice();
    try {
      const rec = (await api('radio', { method: 'POST', body: recent[0] })).items;
      lists = keep;
      set(base + (rec.length ? `<h2>Recommended for you</h2><p class="info" style="color:var(--sub);margin:-8px 0 12px">Because you listened to ${esc(recent[0].title)}</p>${trackTable(rec, { head: false, limit: 15 })}` : ''), true);
    } catch { lists = keep; set(base, true); }
  },
  async search(r, set) {
    const q = r.arg, f = r.extra || 'all';
    if (document.activeElement !== $('#q')) $('#q').value = q;
    if (!q) return set(empty('Search TriTune', 'Find songs, albums and artists from YouTube Music and SoundCloud.'));
    const chips = [['all', 'All'], ['songs', 'Songs'], ['sc', 'SoundCloud'], ['albums', 'Albums'], ['artists', 'Artists']]
      .map(([k, n]) => `<a class="chip${k === f ? ' on' : ''}" href="#/search/${enc(q)}/${k}">${n}</a>`).join('');
    const want = k => f === 'all' || f === k, n = f === 'all' ? 6 : 0;
    set(`<div class="chips">${chips}</div>
      ${want('songs') ? `<section id="s-ytm"><h2>Songs</h2>${skeleton(4)}</section>` : ''}
      ${want('artists') ? '<section id="s-artists"></section>' : ''}
      ${want('albums') ? '<section id="s-albums"></section>' : ''}
      ${want('sc') ? `<section id="s-sc"><h2>From SoundCloud</h2>${skeleton(3)}</section>` : ''}`);
    const token = renderToken;
    const fill = (id, type, html) => api(`search?type=${type}&q=${enc(q)}`).then(d => {
      if (token !== renderToken) return;
      const el = $('#' + id); if (el) el.innerHTML = d.items.length ? html(d.items) : (f === 'all' ? '' : empty('No results', `Nothing found for "${q}"`));
    }).catch(e => { if (token === renderToken) { const el = $('#' + id); if (el) el.innerHTML = ''; fail(e); } });
    if (want('songs')) fill('s-ytm', 'ytm', it => `<h2>Songs</h2>${trackTable(it, { head: false, limit: n })}`);
    if (want('sc')) fill('s-sc', 'sc', it => `<h2>From SoundCloud</h2>${trackTable(it, { head: false, limit: n })}`);
    if (want('artists')) fill('s-artists', 'artists', it => `<h2>Artists</h2><div class="cards${f === 'all' ? ' scroll' : ''}">${it.map(a => card('#/artist/' + enc(a.id), a.thumb, a.name, 'Artist', 'artist')).join('')}</div>`);
    if (want('albums')) fill('s-albums', 'albums', it => `<h2>Albums</h2><div class="cards${f === 'all' ? ' scroll' : ''}">${it.map(a => card('#/album/' + enc(a.id), a.thumb, a.title, [a.year, a.artist].filter(Boolean).join(' • '))).join('')}</div>`);
  },
  async liked(_, set) {
    const tracks = (await api('likes')).items;
    set(hero({ kind: 'Playlist', title: 'Liked Songs', info: total(tracks), tint: '#5038a0', ph: `<div class="ph liked">${svg('heartOn')}</div>` })
      + (tracks.length ? `<div class="actions"><button class="big-play" data-act="play-all"></button></div>${trackTable(tracks)}`
        : empty('Songs you like will appear here', 'Save songs by clicking the heart icon.')));
  },
  async history(_, set) {
    const tracks = (await api('history')).items;
    set(hero({ kind: 'History', title: 'Recently played', info: total(tracks), tint: '#27503f', ph: `<div class="ph">${svg('clock')}</div>` })
      + (tracks.length ? `<div class="actions"><button class="big-play" data-act="play-all"></button></div>${trackTable(tracks)}` : empty('Nothing played yet', '')));
  },
  async playlist(r, set) {
    const p = await api('playlists/' + enc(r.arg));
    set(hero({ kind: 'Playlist', title: p.name, info: total(p.tracks), thumb: p.tracks[0]?.thumb, tint: '#535353' })
      + `<div class="actions">${p.tracks.length ? '<button class="big-play" data-act="play-all"></button>' : ''}
        <button class="icon-btn" data-act="pl-menu" data-pid="${p.id}" data-name="${esc(p.name)}" title="More options">${svg('dots')}</button></div>`
      + (p.tracks.length ? trackTable(p.tracks) : empty("Let's find something for your playlist", 'Search for songs, then right-click → Add to playlist.')));
  },
  async album(r, set) {
    const a = await api('album/' + enc(r.arg));
    const by = a.artist_id ? `<a href="#/artist/${enc(a.artist_id)}"><b>${esc(a.artist)}</b></a>` : `<b>${esc(a.artist)}</b>`;
    set(hero({ kind: 'Album', title: a.title, info: [by, esc(a.year), total(a.tracks)].filter(Boolean).join(' • '), thumb: a.thumb, tint: '#40506a' })
      + `<div class="actions"><button class="big-play" data-act="play-all"></button>
        <button class="icon-btn" data-act="save-album" title="Save to Your Library">${svg('plus')}</button></div>${trackTable(a.tracks)}`);
    VIEWS._album = a;
  },
  async artist(r, set) {
    const a = await api('artist/' + enc(r.arg));
    const cards = (title, items) => items.length ? `<h2>${title}</h2><div class="cards">${items.map(x => card('#/album/' + enc(x.id), x.thumb, x.title, [x.year, 'Album'].filter(Boolean).join(' • '))).join('')}</div>` : '';
    set(hero({ kind: 'Artist', title: a.name, info: esc(a.subscribers ? a.subscribers + ' subscribers' : ''), thumb: a.thumb, tint: '#5a4a3a', cls: 'artist' })
      + (a.tracks.length ? `<div class="actions"><button class="big-play" data-act="play-all"></button></div><h2 style="margin-top:0">Popular</h2>${trackTable(a.tracks, { head: false })}` : '')
      + cards('Albums', a.albums) + cards('Singles and EPs', a.singles));
  },
  async radio(r, set) {
    const seed = JSON.parse(sessionStorage.getItem('radio:' + r.arg) || 'null') || r.arg;
    const tracks = (await api('radio', { method: 'POST', body: seed })).items;
    const all = typeof seed === 'object' ? [seed, ...tracks] : tracks;
    set(hero({ kind: 'Radio', title: (seed.title || 'Song') + ' Radio', info: total(all), thumb: seed.thumb, tint: '#7a3550', ph: seed.thumb ? '' : `<div class="ph">${svg('radio')}</div>` })
      + `<div class="actions"><button class="big-play" data-act="play-all"></button></div>${trackTable(all)}`);
  },
};

async function render() {
  const r = route(), token = ++renderToken, view = VIEWS[r.name] || VIEWS.home;
  hideMenu(); renderSidebar();
  const set = (html, keepScroll) => {
    if (token !== renderToken) return;
    if (!keepScroll) main.scrollTop = 0;
    main.innerHTML = `<div class="view">${html}</div>`; updatePlayBtn();
  };
  lists = [];
  if (r.name !== 'search' && r.name !== 'home') main.innerHTML = `<div class="view" style="padding-top:24px">${skeleton(8)}</div>`;
  try { await view(r, set); } catch (e) {
    if (token === renderToken) main.innerHTML = `<div class="view">${empty('Something went wrong', e.message || String(e))}</div>`;
  }
}
window.addEventListener('hashchange', render);

// ── main area interactions ───────────────────────────────────────────────
main.addEventListener('click', async e => {
  const actEl = e.target.closest('[data-act]');
  if (!actEl) return;
  const act = actEl.dataset.act, row = e.target.closest('[data-l][data-i]');
  const list = row ? lists[row.dataset.l] : null, t = list ? list[row.dataset.i] : null;
  if (act === 'play' && t) {
    if (cur() && cur().id === t.id && audio.src === t.id && actEl.tagName === 'BUTTON') toggle(); else playList(list, +row.dataset.i);
  } else if (act === 'like' && t) toggleLike(t);
  else if (act === 'more' && t) { const b = actEl.getBoundingClientRect(); trackMenu(t, b.left - 200, b.bottom + 4, row); }
  else if (act === 'play-all') {
    const l = mainList();
    if (cur() && l.some(x => x.id === cur().id) && audio.src === cur().id) toggle(); else playList(l, 0);
  } else if (act === 'save-album' && VIEWS._album) {
    const a = VIEWS._album;
    try { await api('playlists', { method: 'POST', body: { name: a.title, tracks: a.tracks } }); await refreshLibrary(); toast('Saved to Your Library'); } catch (err) { fail(err); }
  } else if (act === 'pl-menu') {
    const pid = +actEl.dataset.pid, name = actEl.dataset.name, b = actEl.getBoundingClientRect();
    showMenu(b.left, b.bottom + 4, [
      { label: 'Add to queue', fn: () => enqueue(mainList()) },
      { label: 'Rename', fn: async () => { const n = await ask({ title: 'Rename playlist', value: name, ok: 'Save' }); if (n) { try { await api('playlists/' + pid, { method: 'PATCH', body: { name: n } }); await refreshLibrary(); render(); } catch (err) { fail(err); } } } },
      { label: 'Delete', fn: async () => { if (await ask({ title: 'Delete from Your Library?', text: `This will delete "${name}" from Your Library.`, input: false, ok: 'Delete', danger: true })) { try { await api('playlists/' + pid, { method: 'DELETE' }); await refreshLibrary(); location.hash = '#/home'; } catch (err) { fail(err); } } } },
    ]);
  }
});
main.addEventListener('dblclick', e => {
  const row = e.target.closest('.row');
  if (row && !e.target.closest('button, a')) playList(lists[row.dataset.l], +row.dataset.i);
});
main.addEventListener('contextmenu', e => {
  const row = e.target.closest('[data-l][data-i]');
  if (!row) return;
  e.preventDefault(); hideMenu();
  trackMenu(lists[row.dataset.l][row.dataset.i], e.clientX, e.clientY, row.classList.contains('row') ? row : null);
});

// ── top bar + keyboard ───────────────────────────────────────────────────
let searchTimer;
$('#q').addEventListener('input', e => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => {
    const target = '#/search/' + enc(e.target.value.trim());
    if (route().name === 'search') location.replace(target); else location.hash = target;
  }, 300);
});
$('#q').addEventListener('focus', () => { if (route().name !== 'search' && !$('#q').value) location.hash = '#/search'; });
$('#back').onclick = () => history.back();
$('#fwd').onclick = () => history.forward();
document.addEventListener('keydown', e => {
  const typing = /INPUT|TEXTAREA/.test(document.activeElement.tagName) && document.activeElement.type !== 'range';
  if (e.key === 'Escape') { hideMenu(); if (!$('#modal').hidden) $('#modal-cancel').click(); else if (typing) document.activeElement.blur(); return; }
  if ((e.ctrlKey && e.key.toLowerCase() === 'k') || (e.key === '/' && !typing)) { e.preventDefault(); $('#q').focus(); $('#q').select(); return; }
  if (typing || !$('#modal').hidden) return;
  if (e.code === 'Space') { e.preventDefault(); toggle(); }
  else if (e.ctrlKey && e.key === 'ArrowRight') next(false);
  else if (e.ctrlKey && e.key === 'ArrowLeft') prev();
  else if (e.ctrlKey && e.key === 'ArrowUp') { e.preventDefault(); audio.volume = Math.min(1, audio.volume + .05); updateVol(); }
  else if (e.ctrlKey && e.key === 'ArrowDown') { e.preventDefault(); audio.volume = Math.max(0, audio.volume - .05); updateVol(); }
  else if (e.key.toLowerCase() === 'q' && !e.ctrlKey) toggleQueue();
});
window.addEventListener('beforeunload', saveState);
// No browser context menu anywhere: this is an app window, not a web page.
document.addEventListener('contextmenu', e => { if (!/INPUT|TEXTAREA/.test(e.target.tagName)) e.preventDefault(); });

// ── boot ─────────────────────────────────────────────────────────────────
for (const [id, ic] of Object.entries({ back: 'back', fwd: 'fwd', home: 'home', 'search-ico': 'search', 'lib-ico': 'library', import: 'down', 'new-pl': 'plus', 'queue-close': 'close', shuffle: 'shuffle', prev: 'prev', next: 'next', autoplay: 'radio', 'queue-btn': 'queue' })) $('#' + id).innerHTML = svg(ic);
resumeAt = loadState();
updateVol(); updateModes(); updateNow();
if (cur()) { $('#cur').textContent = fmt(resumeAt); const d = cur().duration; $('#seek').value = d ? resumeAt / d * 1000 : 0; setSlider($('#seek'), d ? resumeAt / d : 0); }
refreshLibrary().catch(fail).finally(render);

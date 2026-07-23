/**
 * GasDex Ratings Worker — Cloudflare Worker
 *
 * Handles:
 * - POST /ballot: Accept and store fan player ratings + MotM pick
 * - GET /aggregate?match_id=...: Return aggregated ratings
 * - GET /ballot-config?match_id=...: Return ballot definition (players, open/close times)
 * - GET /current: Return the current (active or most recent) ballot + its state
 * - GET /auto-status: Last cron run log (for the daily Slack digest / debugging)
 * - scheduled(): matchday cron — auto-creates ballot configs from API-Football
 *   lineups (fallback: full squad), appends subs who came on after full time.
 *   See docs/BALLOT-AUTOMATION.md. Requires the FOOTBALL_API_KEY secret.
 *
 * Storage: KV namespace (GASDEX_RATINGS)
 * Rate limiting: basic IP-based throttle
 * One-ballot-per-fan: localStorage token in ballot body (+ legacy cookie), IP cap backstop
 */

const BALLOT_WINDOW_HOURS = 48;
const RATE_LIMIT_REQUESTS = 10;
const RATE_LIMIT_WINDOW_MINUTES = 15;
// Max accepted ballots per match from one IP address (anti-abuse backstop —
// generous enough for households/shared wifi, stops incognito-loop stuffing).
const IP_VOTE_CAP = 5;

/**
 * Main request router
 * NOTE (module-format workers): KV bindings are NOT globals — they arrive on
 * the `env` object passed to fetch(). Every handler therefore takes `env`
 * and uses env.GASDEX_RATINGS.
 */
async function handleRequest(request, env) {
  const url = new URL(request.url);
  const path = url.pathname;

  // Set CORS headers for all responses (allow-listed site origins only).
  // Allow-Credentials is required because the ballot token rides on a cookie.
  const corsHeaders = {
    'Access-Control-Allow-Origin': getSiteOrigin(request),
    'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
    'Access-Control-Allow-Credentials': 'true',
    'Vary': 'Origin',
    'Cache-Control': 'no-cache'
  };

  // Handle preflight
  if (request.method === 'OPTIONS') {
    return new Response(null, { headers: corsHeaders, status: 204 });
  }

  try {
    // Route dispatch
    if (path === '/ballot' && request.method === 'POST') {
      return await handlePostBallot(request, env, corsHeaders);
    } else if (path === '/aggregate' && request.method === 'GET') {
      return await handleGetAggregate(url, env, corsHeaders);
    } else if (path === '/ballot-config' && request.method === 'GET') {
      return await handleGetBallotConfig(url, env, corsHeaders);
    } else if (path === '/current' && request.method === 'GET') {
      return await handleGetCurrent(env, corsHeaders);
    } else if (path === '/auto-status' && request.method === 'GET') {
      return await handleGetAutoStatus(env, corsHeaders);
    } else {
      return new Response(JSON.stringify({ error: 'not found' }), {
        status: 404,
        headers: { ...corsHeaders, 'Content-Type': 'application/json' }
      });
    }
  } catch (err) {
    console.error('Worker error:', err);
    return new Response(JSON.stringify({ error: 'internal server error' }), {
      status: 500,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' }
    });
  }
}

/**
 * POST /ballot
 * Accepts { match_id, scores: {player_name: 1-10, ...}, motm: player_name }
 */
async function handlePostBallot(request, env, corsHeaders) {
  const clientIp = request.headers.get('CF-Connecting-IP') || 'unknown';

  // Rate limit check
  const rateLimitKey = `rate:${clientIp}`;
  const rateLimitData = await env.GASDEX_RATINGS.get(rateLimitKey, 'json') || { count: 0, resetAt: Date.now() + RATE_LIMIT_WINDOW_MINUTES * 60000 };

  if (Date.now() < rateLimitData.resetAt && rateLimitData.count >= RATE_LIMIT_REQUESTS) {
    return new Response(JSON.stringify({ error: 'rate limited' }), {
      status: 429,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' }
    });
  }

  // Increment rate limit
  if (Date.now() >= rateLimitData.resetAt) {
    rateLimitData.count = 1;
    rateLimitData.resetAt = Date.now() + RATE_LIMIT_WINDOW_MINUTES * 60000;
  } else {
    rateLimitData.count += 1;
  }
  await env.GASDEX_RATINGS.put(rateLimitKey, JSON.stringify(rateLimitData));

  // Parse payload
  let payload;
  try {
    payload = await request.json();
  } catch (e) {
    return new Response(JSON.stringify({ error: 'invalid JSON' }), {
      status: 400,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' }
    });
  }

  const { match_id, scores, motm } = payload;

  // Validation
  if (!match_id || typeof match_id !== 'string' || match_id.trim() === '') {
    return new Response(JSON.stringify({ error: 'missing or invalid match_id' }), {
      status: 400,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' }
    });
  }

  if (!scores || typeof scores !== 'object' || Object.keys(scores).length === 0) {
    return new Response(JSON.stringify({ error: 'missing or empty scores object' }), {
      status: 400,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' }
    });
  }

  if (!motm || typeof motm !== 'string' || motm.trim() === '') {
    return new Response(JSON.stringify({ error: 'missing or invalid motm' }), {
      status: 400,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' }
    });
  }

  // Validate scores: all must be integers 1-10
  for (const [player, score] of Object.entries(scores)) {
    if (!Number.isInteger(score) || score < 1 || score > 10) {
      return new Response(JSON.stringify({ error: `invalid score for ${player}: must be integer 1-10` }), {
        status: 400,
        headers: { ...corsHeaders, 'Content-Type': 'application/json' }
      });
    }
  }

  // Validate motm is in scores
  if (!(motm in scores)) {
    return new Response(JSON.stringify({ error: 'motm player not in scores' }), {
      status: 400,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' }
    });
  }

  // Check ballot window for match
  const ballotConfig = await env.GASDEX_RATINGS.get(`config:${match_id}`, 'json');
  if (!ballotConfig) {
    return new Response(JSON.stringify({ error: 'ballot not open for this match' }), {
      status: 400,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' }
    });
  }

  const now = Date.now();
  const openTime = new Date(ballotConfig.openAt).getTime();
  if (Number.isFinite(openTime) && now < openTime) {
    return new Response(JSON.stringify({ error: 'ballot not yet open' }), {
      status: 400,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' }
    });
  }
  const closeTime = new Date(ballotConfig.closeAt).getTime();
  if (now > closeTime) {
    return new Response(JSON.stringify({ error: 'ballot window has closed' }), {
      status: 400,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' }
    });
  }

  // Only players on the ballot may be scored (stops junk names polluting the
  // aggregate). Configs may store players as strings or {name, pos} objects.
  const allowedNames = configPlayerNames(ballotConfig);
  if (allowedNames.length > 0) {
    for (const player of Object.keys(scores)) {
      if (!allowedNames.includes(player)) {
        return new Response(JSON.stringify({ error: `unknown player: ${player}` }), {
          status: 400,
          headers: { ...corsHeaders, 'Content-Type': 'application/json' }
        });
      }
    }
  }

  // One-ballot-per-fan. The token is the voter identity and travels TWO ways:
  //  1. In the request BODY (payload.ballot_token) — the page keeps it in
  //     localStorage. This is FIRST-PARTY storage, so it survives in Brave /
  //     Safari / Firefox, which all bin or expire the cross-site cookie
  //     (live bug: Brave's ephemeral third-party storage let the same
  //     browser revote in a new session).
  //  2. As a cookie (legacy backup for browsers that kept it).
  // Body token wins; cookie is the fallback; otherwise mint a fresh one.
  // The token is echoed back in the response body so the page can store it.
  let ballotToken = sanitizeToken(payload.ballot_token) || getBallotToken(request);
  if (!ballotToken) {
    ballotToken = generateToken();
  }
  // Key on the TOKEN ONLY (not IP+token): a fan whose IP changes (mobile
  // networks) must still be blocked from revoting with the same browser.
  const voterKey = hashToken(ballotToken);
  const voterRecord = await env.GASDEX_RATINGS.get(`voter:${match_id}:${voterKey}`);

  if (voterRecord) {
    return new Response(JSON.stringify({ error: 'you have already voted on this match' }), {
      status: 400,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' }
    });
  }

  // IP cap backstop: at most IP_VOTE_CAP accepted ballots per match from one
  // IP. Catches token-reset abuse (incognito loops / cleared storage) while
  // leaving room for households and shared wifi. Carrier-NAT fans could in
  // theory exhaust a shared IP on a big match — cap is tunable.
  const ipCapKey = `ipvotes:${match_id}:${hashIp(clientIp)}`;
  const ipVotes = parseInt(await env.GASDEX_RATINGS.get(ipCapKey) || '0', 10);
  if (ipVotes >= IP_VOTE_CAP) {
    return new Response(JSON.stringify({ error: 'vote limit reached for this network' }), {
      status: 400,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' }
    });
  }

  // Store ballot
  const ballotId = generateId();
  const ballot = {
    id: ballotId,
    match_id,
    scores,
    motm,
    timestamp: new Date().toISOString(),
    clientIp: hashIp(clientIp) // store hashed IP only
  };

  await env.GASDEX_RATINGS.put(`ballot:${ballotId}`, JSON.stringify(ballot));
  await env.GASDEX_RATINGS.put(`voter:${match_id}:${voterKey}`, 'voted');
  await env.GASDEX_RATINGS.put(ipCapKey, String(ipVotes + 1));

  // Register the ballot in the per-match index so /aggregate can find it.
  // (Read-modify-write is fine at this traffic level; see backend-notes.md.)
  const ballotListKey = `ballots:${match_id}`;
  const ballotList = await env.GASDEX_RATINGS.get(ballotListKey, 'json') || [];
  ballotList.push(ballotId);
  await env.GASDEX_RATINGS.put(ballotListKey, JSON.stringify(ballotList));

  // Echo the token in the body (the page stores it in localStorage — the
  // reliable path) AND keep the legacy cookie (SameSite=None + Secure because
  // the site and worker are on different hosts; some browsers won't keep it).
  return new Response(JSON.stringify({ ok: true, ballot_id: ballotId, ballot_token: ballotToken }), {
    status: 200,
    headers: {
      ...corsHeaders,
      'Content-Type': 'application/json',
      'Set-Cookie': `gasdex-ballot-token=${ballotToken}; Max-Age=31536000; Path=/; Secure; HttpOnly; SameSite=None`
    }
  });
}

/**
 * GET /aggregate?match_id=...
 * Returns aggregated ratings: { match_id, count, players: {name: {avg, motm_votes}} }
 */
async function handleGetAggregate(url, env, corsHeaders) {
  const matchId = url.searchParams.get('match_id');

  if (!matchId || matchId.trim() === '') {
    return new Response(JSON.stringify({ error: 'missing match_id' }), {
      status: 400,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' }
    });
  }

  // Fetch all ballots for this match (in production, use a proper index; this is simplified)
  // For now, we'll assume ballots are keyed ballot:* and we iterate; in real Cloudflare,
  // you'd maintain a list or use bulk operations more efficiently.
  // PROVISIONAL: this scales poorly; see backend-notes.md for recommendations.

  const ballots = [];
  const prefix = 'ballot:';

  // Cloudflare KV doesn't have efficient list by prefix in free tier.
  // PROVISIONAL: for MVP, store match index separately, or accept this limitation.
  // Store a rolling list of ballot IDs per match.

  const ballotListKey = `ballots:${matchId}`;
  const ballotList = await env.GASDEX_RATINGS.get(ballotListKey, 'json') || [];

  for (const ballotId of ballotList) {
    const ballot = await env.GASDEX_RATINGS.get(`ballot:${ballotId}`, 'json');
    if (ballot && ballot.match_id === matchId) {
      ballots.push(ballot);
    }
  }

  if (ballots.length === 0) {
    return new Response(JSON.stringify({
      match_id: matchId,
      count: 0,
      players: {}
    }), {
      status: 200,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' }
    });
  }

  // Aggregate scores
  const players = {};
  let motmCounts = {};

  for (const ballot of ballots) {
    for (const [player, score] of Object.entries(ballot.scores)) {
      if (!players[player]) {
        players[player] = { scores: [], motm_votes: 0 };
      }
      players[player].scores.push(score);
    }
    motmCounts[ballot.motm] = (motmCounts[ballot.motm] || 0) + 1;
  }

  // Calculate averages
  const result = {};
  for (const [player, data] of Object.entries(players)) {
    const avg = (data.scores.reduce((a, b) => a + b, 0) / data.scores.length).toFixed(1);
    result[player] = {
      avg: parseFloat(avg),
      motm_votes: motmCounts[player] || 0
    };
  }

  return new Response(JSON.stringify({
    match_id: matchId,
    count: ballots.length,
    players: result
  }), {
    status: 200,
    headers: { ...corsHeaders, 'Content-Type': 'application/json' }
  });
}

/**
 * GET /ballot-config?match_id=...
 * Returns ballot definition for a match: { match_id, players: [name, ...], openAt, closeAt }
 */
async function handleGetBallotConfig(url, env, corsHeaders) {
  const matchId = url.searchParams.get('match_id');

  if (!matchId || matchId.trim() === '') {
    return new Response(JSON.stringify({ error: 'missing match_id' }), {
      status: 400,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' }
    });
  }

  const config = await env.GASDEX_RATINGS.get(`config:${matchId}`, 'json');

  if (!config) {
    return new Response(JSON.stringify({ error: 'ballot not found' }), {
      status: 404,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' }
    });
  }

  return new Response(JSON.stringify(config), {
    status: 200,
    headers: { ...corsHeaders, 'Content-Type': 'application/json' }
  });
}

/**
 * GET /current
 * Returns the current ballot (the one the cron — or a manual seed — last
 * pointed the `current` KV key at) plus its live state, so the pages never
 * need a hard-coded match id:
 *   { status: 'none' | 'upcoming' | 'open' | 'closed', match_id, label,
 *     fixture, openAt, closeAt, source, players: [{name, pos}] }
 */
async function handleGetCurrent(env, corsHeaders) {
  const jsonHeaders = { ...corsHeaders, 'Content-Type': 'application/json' };
  const current = await env.GASDEX_RATINGS.get('current', 'json');
  if (!current || !current.match_id) {
    return new Response(JSON.stringify({ status: 'none' }), { status: 200, headers: jsonHeaders });
  }
  const config = await env.GASDEX_RATINGS.get(`config:${current.match_id}`, 'json');
  if (!config) {
    return new Response(JSON.stringify({ status: 'none' }), { status: 200, headers: jsonHeaders });
  }
  const now = Date.now();
  const openAt = new Date(config.openAt).getTime();
  const closeAt = new Date(config.closeAt).getTime();
  let status = 'open';
  if (Number.isFinite(openAt) && now < openAt) status = 'upcoming';
  else if (Number.isFinite(closeAt) && now > closeAt) status = 'closed';
  const players = (config.players || []).map(function (p) {
    return typeof p === 'string' ? { name: p, pos: '' } : { name: p.name, pos: p.pos || '' };
  });
  return new Response(JSON.stringify({
    status,
    match_id: current.match_id,
    label: config.label || '',
    fixture: config.fixture || null,
    openAt: config.openAt || null,
    closeAt: config.closeAt || null,
    source: config.source || 'manual',
    players
  }), { status: 200, headers: jsonHeaders });
}

/**
 * GET /auto-status — last cron run log (read-only; used by the Slack digest).
 */
async function handleGetAutoStatus(env, corsHeaders) {
  const log = await env.GASDEX_RATINGS.get('auto:log', 'json');
  return new Response(JSON.stringify(log || { note: 'cron has not run yet' }), {
    status: 200,
    headers: { ...corsHeaders, 'Content-Type': 'application/json' }
  });
}

/* ========================================================================== *
 * BALLOT AUTOMATION (matchday cron)
 *
 * Runs every 5 minutes (wrangler.toml [triggers]) and NO-OPS instantly —
 * zero API calls — unless the current time is inside a matchday window
 * taken from the site's own published fixtures (out/fixtures.json, built
 * from TheSportsDB + the maintainer's overrides file).
 *
 * Matchday flow (frugal by design — ~15-20 API calls per matchday):
 *   KO-60m .. KO+3h : poll /fixtures/lineups every ~5 min until the real XI
 *                     lands, then write config:<match_id> (openAt = kickoff,
 *                     closeAt = kickoff + 50h ≈ full time + 48h) and stop.
 *   KO, no lineups  : fall back to a full-squad ballot (cached squad, one
 *                     API call a month) so voting ALWAYS opens at kickoff;
 *                     lineup polling continues and upgrades it in place.
 *   KO+105m onward  : once the fixture reports FT, one /fixtures/events call
 *                     appends the subs who actually came on. Done.
 *
 * The API key is the FOOTBALL_API_KEY secret (wrangler secret put) — it is
 * never present in this repo. Without it the cron logs and does nothing.
 * ========================================================================== */

const AF_BASE = 'https://v3.football.api-sports.io';
const AF_TEAM_ID = 1334;      // Bristol Rovers on API-Football
const AF_SEASON = 2026;       // 2026/27
const SITE_FIXTURES_URL = 'https://marrowsplat.github.io/gasdex/fixtures.json';
const CLOSE_HOURS_AFTER_KO = 50;      // ≈ "48 hours after full time"
const LINEUP_POLL_START_MIN = 60;     // start polling an hour before kickoff
const LINEUP_POLL_SPACING_MS = 4.5 * 60000;
const EVENTS_POLL_SPACING_MS = 10 * 60000;

async function runCron(env, now) {
  now = now || Date.now();
  const log = { ran_at: new Date(now).toISOString(), actions: [], api_calls: 0 };
  try {
    const fixtures = await getSiteFixtures(env, now, log);
    const fx = pickActiveFixture(fixtures, now);
    if (!fx) {
      log.actions.push('no matchday window');
      return log;
    }
    log.match_id = fx.match_id;
    await runMatchday(env, fx, now, log);
  } catch (e) {
    log.error = String((e && e.message) || e);
  } finally {
    try { await env.GASDEX_RATINGS.put('auto:log', JSON.stringify(log)); } catch (e) { /* best-effort */ }
  }
  return log;
}

async function runMatchday(env, fx, now, log) {
  const ko = fx.ko;
  const stateKey = `auto:state:${fx.match_id}`;
  const cfgKey = `config:${fx.match_id}`;
  const state = await env.GASDEX_RATINGS.get(stateKey, 'json') || {};
  let config = await env.GASDEX_RATINGS.get(cfgKey, 'json');

  // 1. Resolve the API-Football fixture id (cached season map, by date).
  if (!state.afId) {
    const map = await getAfFixtureMap(env, now, log);
    state.afId = (map && map[fx.date]) || null;
    if (!state.afId) log.actions.push(`no API fixture id for ${fx.date}`);
  }

  // 2. Lineup polling — pre-KO for the real XI; keeps going after KO so a
  //    squad-fallback ballot gets upgraded the moment lineups land.
  const lineupWindow = now >= ko - LINEUP_POLL_START_MIN * 60000 && now <= ko + 3 * 3600000;
  if (state.afId && !state.lineupsDone && lineupWindow &&
      (!state.lastLineupPoll || now - state.lastLineupPoll >= LINEUP_POLL_SPACING_MS)) {
    state.lastLineupPoll = now;
    const players = await afLineups(env, state.afId, log);
    if (players && players.length) {
      config = buildBallotConfig(fx, ko, players, 'lineups');
      await env.GASDEX_RATINGS.put(cfgKey, JSON.stringify(config));
      await setCurrent(env, fx.match_id);
      state.lineupsDone = true;
      log.actions.push(`config written from lineups (${players.length} players)`);
    } else {
      log.actions.push('lineups not available yet');
    }
  }

  // 3. Kickoff fallback: voting must ALWAYS open at KO. No lineups yet →
  //    open a full-squad ballot (upgraded in place when lineups arrive).
  if (!config && now >= ko) {
    const squad = await getSquad(env, now, log);
    if (squad && squad.length) {
      config = buildBallotConfig(fx, ko, squad, 'squad');
      await env.GASDEX_RATINGS.put(cfgKey, JSON.stringify(config));
      await setCurrent(env, fx.match_id);
      log.actions.push(`config written from squad fallback (${squad.length} players)`);
    } else {
      log.actions.push('squad fallback unavailable');
    }
  }

  // 4. Post-match: when the fixture reports full time, append the subs who
  //    actually came on (one events call), then stop for good.
  if (config && state.afId && !state.eventsDone && now >= ko + 105 * 60000 &&
      (!state.lastEventsPoll || now - state.lastEventsPoll >= EVENTS_POLL_SPACING_MS)) {
    state.lastEventsPoll = now;
    const status = await afFixtureStatus(env, state.afId, log);
    if (status && ['FT', 'AET', 'PEN'].indexOf(status) !== -1) {
      const subs = await afSubsOn(env, state.afId, log);
      if (subs && subs.length) {
        const names = configPlayerNames(config);
        subs.forEach(function (s) {
          if (names.indexOf(s.name) === -1) config.players.push(s);
        });
        await env.GASDEX_RATINGS.put(cfgKey, JSON.stringify(config));
        log.actions.push(`appended ${subs.length} subs from events`);
      } else {
        log.actions.push('no substitution events returned');
      }
      state.eventsDone = true;
      state.lineupsDone = true; // no further lineup polling after FT
    } else if (now > ko + 5 * 3600000) {
      state.eventsDone = true;  // give up quietly ~5h after KO
      log.actions.push('gave up waiting for FT status');
    } else {
      log.actions.push(`fixture status ${status || 'unknown'} — waiting for FT`);
    }
  }

  await env.GASDEX_RATINGS.put(stateKey, JSON.stringify(state));
}

function buildBallotConfig(fx, ko, players, source) {
  return {
    match_id: fx.match_id,
    label: 'vs ' + fx.opponent + ' (' + fx.venue + ')',
    fixture: {
      opponent: fx.opponent,
      venue: fx.venue,
      competition: fx.competition || '',
      date: fx.date,
      kickoff: fx.kickoff || ''
    },
    openAt: new Date(ko).toISOString(),
    closeAt: new Date(ko + CLOSE_HOURS_AFTER_KO * 3600000).toISOString(),
    source: source,
    players: players
  };
}

async function setCurrent(env, matchId) {
  await env.GASDEX_RATINGS.put('current', JSON.stringify({
    match_id: matchId,
    set_at: new Date().toISOString()
  }));
}

function configPlayerNames(config) {
  return (config.players || []).map(function (p) {
    return typeof p === 'string' ? p : p.name;
  });
}

/* ---- site fixtures (free — fetched from our own published JSON) ---------- */

async function getSiteFixtures(env, now, log) {
  const cacheKey = 'auto:fixtures';
  const cached = await env.GASDEX_RATINGS.get(cacheKey, 'json');
  if (cached && cached.fetched_at && now - cached.fetched_at < 6 * 3600000) {
    return cached.fixtures || [];
  }
  const url = env.FIXTURES_URL || SITE_FIXTURES_URL;
  try {
    const res = await fetch(url, { headers: { 'Accept': 'application/json' } });
    if (!res.ok) throw new Error('fixtures fetch HTTP ' + res.status);
    const data = await res.json();
    const fixtures = (data.fixtures || []).filter(function (f) { return f && f.match_id && f.date; });
    await env.GASDEX_RATINGS.put(cacheKey, JSON.stringify({ fetched_at: now, fixtures: fixtures }));
    log.actions.push(`fixtures refreshed (${fixtures.length})`);
    return fixtures;
  } catch (e) {
    log.actions.push('fixtures fetch failed: ' + String((e && e.message) || e));
    return (cached && cached.fixtures) || [];
  }
}

function pickActiveFixture(fixtures, now) {
  // "Matchday window" = from 70 min before kickoff until 6 h after — wide
  // enough for lineup polling, the KO fallback and the post-FT events call.
  for (const f of fixtures) {
    if (f.tbc) continue;
    const ko = londonToEpoch(f.date, f.kickoff || '15:00');
    if (!Number.isFinite(ko)) continue;
    if (now >= ko - 70 * 60000 && now <= ko + 6 * 3600000) {
      return Object.assign({}, f, { ko: ko });
    }
  }
  return null;
}

/* Fixture kickoffs are London wall-clock times; Workers run in UTC. Convert
 * via Intl (two-pass offset trick — handles GMT/BST automatically). */
function londonToEpoch(dateStr, timeStr) {
  const guess = Date.parse(dateStr + 'T' + timeStr + ':00Z');
  if (!Number.isFinite(guess)) return NaN;
  return guess - londonOffsetMs(guess);
}

function londonOffsetMs(epoch) {
  const dtf = new Intl.DateTimeFormat('en-GB', {
    timeZone: 'Europe/London', hour12: false,
    year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit'
  });
  const parts = {};
  dtf.formatToParts(epoch).forEach(function (p) { parts[p.type] = p.value; });
  const hour = parts.hour === '24' ? '00' : parts.hour;
  const asUtc = Date.parse(parts.year + '-' + parts.month + '-' + parts.day + 'T' + hour + ':' + parts.minute + ':00Z');
  return asUtc - epoch;
}

/* ---- API-Football calls (metered; all responses cached where reusable) --- */

async function afGet(env, path, log) {
  if (!env.FOOTBALL_API_KEY) {
    log.actions.push('FOOTBALL_API_KEY secret not set — skipping API call');
    return null;
  }
  log.api_calls += 1;
  try {
    const res = await fetch(AF_BASE + path, { headers: { 'x-apisports-key': env.FOOTBALL_API_KEY } });
    if (!res.ok) {
      log.actions.push('API HTTP ' + res.status + ' for ' + path);
      return null;
    }
    const data = await res.json();
    if (data.errors && Object.keys(data.errors).length) {
      log.actions.push('API error for ' + path + ': ' + JSON.stringify(data.errors));
      return null;
    }
    return data;
  } catch (e) {
    log.actions.push('API fetch failed for ' + path + ': ' + String((e && e.message) || e));
    return null;
  }
}

async function getAfFixtureMap(env, now, log) {
  const cacheKey = 'auto:afmap';
  const cached = await env.GASDEX_RATINGS.get(cacheKey, 'json');
  if (cached && cached.fetched_at && now - cached.fetched_at < 7 * 86400000) {
    return cached.map || {};
  }
  const data = await afGet(env, `/fixtures?team=${AF_TEAM_ID}&season=${AF_SEASON}`, log);
  if (!data) return (cached && cached.map) || {};
  const map = {};
  (data.response || []).forEach(function (r) {
    const iso = r.fixture && r.fixture.date;   // ISO with offset
    const id = r.fixture && r.fixture.id;
    if (!iso || !id) return;
    map[londonDateOf(new Date(iso).getTime())] = id;
  });
  await env.GASDEX_RATINGS.put(cacheKey, JSON.stringify({ fetched_at: now, map: map }));
  log.actions.push(`AF fixture map refreshed (${Object.keys(map).length})`);
  return map;
}

function londonDateOf(epoch) {
  const dtf = new Intl.DateTimeFormat('en-CA', { timeZone: 'Europe/London', year: 'numeric', month: '2-digit', day: '2-digit' });
  return dtf.format(epoch);   // YYYY-MM-DD
}

async function afLineups(env, afId, log) {
  const data = await afGet(env, `/fixtures/lineups?fixture=${afId}`, log);
  if (!data || !data.response || !data.response.length) return null;
  const rovers = data.response.filter(function (r) { return r.team && r.team.id === AF_TEAM_ID; })[0];
  if (!rovers || !rovers.startXI || !rovers.startXI.length) return null;
  return rovers.startXI.map(function (p) {
    return { name: p.player.name, pos: posShort(p.player.pos) };
  });
}

async function afFixtureStatus(env, afId, log) {
  const data = await afGet(env, `/fixtures?id=${afId}`, log);
  if (!data || !data.response || !data.response.length) return null;
  const f = data.response[0].fixture;
  return (f && f.status && f.status.short) || null;
}

async function afSubsOn(env, afId, log) {
  const data = await afGet(env, `/fixtures/events?fixture=${afId}&team=${AF_TEAM_ID}&type=subst`, log);
  if (!data || !data.response) return null;
  const out = [];
  data.response.forEach(function (e) {
    // For substitution events the incoming player is in `assist`.
    const name = e.assist && e.assist.name;
    if (name && !out.some(function (s) { return s.name === name; })) {
      out.push({ name: name, pos: '' });
    }
  });
  return out;
}

async function getSquad(env, now, log) {
  const cacheKey = 'auto:squad';
  const cached = await env.GASDEX_RATINGS.get(cacheKey, 'json');
  if (cached && cached.fetched_at && now - cached.fetched_at < 30 * 86400000) {
    return cached.players || [];
  }
  const data = await afGet(env, `/players/squads?team=${AF_TEAM_ID}`, log);
  if (!data || !data.response || !data.response.length) return (cached && cached.players) || [];
  const players = (data.response[0].players || []).map(function (p) {
    return { name: p.name, pos: posShort((p.position || '').charAt(0)) };
  });
  await env.GASDEX_RATINGS.put(cacheKey, JSON.stringify({ fetched_at: now, players: players }));
  log.actions.push(`squad refreshed (${players.length})`);
  return players;
}

function posShort(p) {
  return { G: 'GK', D: 'DF', M: 'MF', F: 'FW', A: 'FW' }[p] || '';
}

/**
 * Helpers
 */

const ALLOWED_ORIGINS = [
  'https://gasdex.co.uk',
  'https://www.gasdex.co.uk',
  'https://marrowsplat.github.io',
];

function getSiteOrigin(request) {
  // Echo the requesting page's Origin when it is on the allow-list; this is
  // what makes cross-origin fetch() from the site work (the worker lives on
  // its own hostname). Localhost is allowed for development.
  const origin = request.headers.get('Origin') || '';
  if (ALLOWED_ORIGINS.includes(origin)) return origin;
  if (/^https?:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/.test(origin)) return origin;
  // Non-CORS requests (same-origin or curl) get the canonical site origin.
  return ALLOWED_ORIGINS[0];
}

function getBallotToken(request) {
  // Extract the ballot token from cookies. Returns null if absent — the
  // ballot handler then mints one and returns it via Set-Cookie.
  const cookieHeader = request.headers.get('Cookie') || '';
  const match = cookieHeader.match(/gasdex-ballot-token=([^;]+)/);
  return match ? match[1] : null;
}

function generateToken() {
  return Math.random().toString(36).substring(2, 15) + Math.random().toString(36).substring(2, 15);
}

function sanitizeToken(t) {
  // Body tokens are client-supplied — accept only plausible token strings so
  // junk can't be stored or reflected. Returns null if invalid/absent.
  if (typeof t !== 'string') return null;
  return /^[a-z0-9]{10,64}$/.test(t) ? t : null;
}

function hashToken(token) {
  // Voter identity hash — token only (see handlePostBallot for why not IP).
  return token.split('').reduce((acc, ch) => {
    return (acc << 5) - acc + ch.charCodeAt(0);
  }, 0).toString(36);
}

function hashIp(ip) {
  // Hash IP for privacy (never store raw IPs)
  return ip.split('').reduce((acc, ch) => {
    return (acc << 5) - acc + ch.charCodeAt(0);
  }, 0).toString(36);
}

function generateId() {
  return `ballot_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;
}

/**
 * Export for Cloudflare Workers
 */
export default {
  fetch(request, env, ctx) {
    return handleRequest(request, env);
  },
  scheduled(event, env, ctx) {
    ctx.waitUntil(runCron(env));
  }
};

// Exposed for the node test harness (mocked KV + fetch).
export { runCron, pickActiveFixture, londonToEpoch, buildBallotConfig };

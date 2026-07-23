/**
 * GasDex Ratings Worker — Cloudflare Worker
 *
 * Handles:
 * - POST /ballot: Accept and store fan player ratings + MotM pick
 * - GET /aggregate?match_id=...: Return aggregated ratings
 * - GET /ballot-config?match_id=...: Return ballot definition (players, open/close times)
 *
 * Storage: KV namespace (GASDEX_RATINGS)
 * Rate limiting: basic IP-based throttle
 * One-ballot-per-fan: hashed IP + browser token cookie (best-effort, documented limits)
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
  const closeTime = new Date(ballotConfig.closeAt).getTime();
  if (now > closeTime) {
    return new Response(JSON.stringify({ error: 'ballot window has closed' }), {
      status: 400,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' }
    });
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
  }
};

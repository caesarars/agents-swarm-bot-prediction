const BASE = import.meta.env.VITE_API_BASE || ''

async function getJson(path) {
  const r = await fetch(`${BASE}/api${path}`)
  if (!r.ok) throw new Error(`${path} -> ${r.status}`)
  return r.json()
}

async function postJson(path) {
  const r = await fetch(`${BASE}/api${path}`, { method: 'POST' })
  if (!r.ok) throw new Error(`${path} -> ${r.status}`)
  return r.json()
}

export const api = {
  latest: () => getJson('/predictions/latest').catch(() => null),
  history: (limit = 30) => getJson(`/predictions/history?limit=${limit}`),
  votes: (id) => getJson(`/predictions/${id}/votes`),
  agents: () => getJson('/agents'),
  stats: () => getJson('/stats'),
  snapshot: () => getJson('/market/snapshot'),
  polymarket: () => getJson('/polymarket/btc'),
  runNow: () => postJson('/predict/run'),
  settleNow: () => postJson('/predict/settle'),
}

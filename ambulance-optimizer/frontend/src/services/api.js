const BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1'
const WS = 'ws://localhost:8000/api/v1'
// const WS   = import.meta.env.VITE_WS_URL  || 'ws://localhost:8000/api/v1'
// const WS = import.meta.env.VITE_WS_URL || 'ws://localhost:8000'

async function req(path, opts = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...opts.headers },
    ...opts,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ message: 'Request failed' }))
    throw Object.assign(new Error(err.message || 'Error'), { status: res.status, code: err.error })
  }
  return res.json()
}

export const incidentsApi = {
  list:   ()       => req('/incidents'),
  get:    (id)     => req(`/incidents/${id}`),
  create: (data)   => req('/incidents', { method: 'POST', body: JSON.stringify(data) }),
  updateStatus: (id, status, notes) =>
    req(`/incidents/${id}/status`, { method: 'PATCH', body: JSON.stringify({ status, notes }) }),
}

export const ambulancesApi = {
  list:      ()     => req('/ambulances'),
  available: ()     => req('/ambulances/available'),
  register:  (data) => req('/ambulances', { method: 'POST', body: JSON.stringify(data) }),
  updateStatus: (id, status) =>
    req(`/ambulances/${id}/status`, { method: 'PATCH', body: JSON.stringify({ status }) }),
}

export const dispatchApi = {
  trigger: (incidentId) => req(`/dispatch/${incidentId}`, { method: 'POST' }),
}

export const dashboardApi = {
  summary: ()         => req('/dashboard/summary'),
  metrics: ()         => req('/dashboard/metrics'),
  heatmap: (days = 7) => req(`/dashboard/incidents/heatmap?days=${days}`),
}

export const healthApi = {
  check: () => fetch(BASE.replace('/api/v1', '') + '/health').then(r => r.json()),
}

// export function createDashboardWS(onMessage) {
//   const ws = new WebSocket(`${WS}/ws/dashboard`)
//   ws.onmessage = (e) => {
//     try {
//       const msg = JSON.parse(e.data)
//       if (msg.event === 'ping') ws.send(JSON.stringify({ event: 'pong' }))
//       else onMessage(msg)
//     } catch {}
//   }
//   return ws
// }

export function createDashboardWS(onMessage) {
  return new WebSocket("ws://localhost:8000/api/v1/ws/dashboard")
  // const ws = new WebSocket("ws://localhost:8000/api/v1/ws/dashboard")

  // ws.onopen = () => {
  //   console.log("✅ Dashboard WS Connected")
  // }

  // ws.onmessage = (e) => {
  //   try {
  //     const msg = JSON.parse(e.data)
  //     if (msg.event === 'ping') {
  //       ws.send(JSON.stringify({ event: 'pong' }))
  //     } else {
  //       onMessage(msg)
  //     }
  //   } catch {}
  // }

  // ws.onerror = (e) => {
  //   console.error("❌ WS Error", e)
  // }

  // ws.onclose = () => {
  //   console.log("❌ WS Closed")
  // }

  // return ws
}
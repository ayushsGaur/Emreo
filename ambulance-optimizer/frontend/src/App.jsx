import { useEffect, useState, useCallback } from 'react'
import { AnimatePresence } from 'framer-motion'
import { Toaster } from 'react-hot-toast'
import { StoreProvider, useStore } from './store/useStore.jsx'
import { useWebSocket } from './hooks/useWebSocket.js'
import { incidentsApi, ambulancesApi, dashboardApi } from './services/api.js'
import Header from './components/Header.jsx'
import LiveTicker from './components/LiveTicker.jsx'
import IncidentPanel from './components/incidents/IncidentPanel.jsx'
import LiveMap from './components/map/LiveMap.jsx'
import RightPanel from './components/RightPanel.jsx'
import IncidentForm from './components/incidents/IncidentForm.jsx'
import "leaflet/dist/leaflet.css";
import { useMemo } from "react"


function AppInner() {
  const { state, dispatch } = useStore()
  const [rightVisible, setRightVisible] = useState(true)

  /* ── WebSocket handlers ──────────────────────── */
  // const handlers = {
  //   'incident.new': useCallback((data) => {
  //     incidentsApi.get(data.incident_id)
  //       .then(inc => dispatch({ type: 'ADD_INCIDENT', payload: inc }))
  //       .catch(() => {})
  //   }, [dispatch]),

  //   'incident.status_changed': useCallback((data) => {
  //     dispatch({ type: 'UPDATE_INCIDENT', payload: { id: data.incident_id, status: data.new_status } })
  //   }, [dispatch]),

  //   'dispatch.completed': useCallback((data) => {
  //     dispatch({ type: 'UPDATE_INCIDENT', payload: {
  //       id:                          data.incident_id,
  //       status:                      'dispatched',
  //       assigned_ambulance_id:       data.ambulance_id,
  //       estimated_arrival_minutes:   data.eta_minutes,
  //     }})
  //   }, [dispatch]),

  //   'ambulance.location': useCallback((data) => {
  //     dispatch({ type: 'UPDATE_AMB_LOC', payload: data })
  //   }, [dispatch]),

  //   'ambulance.status_changed': useCallback((data) => {
  //     dispatch({ type: 'UPDATE_AMB_STATUS', payload: data })
  //   }, [dispatch]),
  // }
  const handlers = useMemo(() => ({
  'incident.new': (data) => {
    incidentsApi.get(data.incident_id)
      .then(inc => dispatch({ type: 'ADD_INCIDENT', payload: inc }))
      .catch(() => {})
  },

  'incident.status_changed': (data) => {
    dispatch({
      type: 'UPDATE_INCIDENT',
      payload: { id: data.incident_id, status: data.new_status }
    })
  },

  'dispatch.completed': (data) => {
    dispatch({
      type: 'UPDATE_INCIDENT',
      payload: {
        id: data.incident_id,
        status: 'dispatched',
        assigned_ambulance_id: data.ambulance_id,
        estimated_arrival_minutes: data.eta_minutes,
      }
    })
  },

  'ambulance.location': (data) => {
    dispatch({ type: 'UPDATE_AMB_LOC', payload: data })
  },

  'ambulance.status_changed': (data) => {
    dispatch({ type: 'UPDATE_AMB_STATUS', payload: data })
  },

}), [dispatch])

  const { status: wsStatus } = useWebSocket(handlers)

  /* ── Initial data load ───────────────────────── */
  useEffect(() => {
    incidentsApi.list()
      .then(d => dispatch({ type: 'SET_INCIDENTS', payload: d }))
      .catch(console.error)

    ambulancesApi.list()
      .then(d => dispatch({ type: 'SET_AMBULANCES', payload: d }))
      .catch(console.error)

    dashboardApi.summary()
      .then(d => dispatch({ type: 'SET_SUMMARY', payload: d }))
      .catch(console.error)

    // Poll summary every 30s
    const t = setInterval(() => {
      dashboardApi.summary()
        .then(d => dispatch({ type: 'SET_SUMMARY', payload: d }))
        .catch(console.error)
    }, 30_000)

    return () => clearInterval(t)
  }, [dispatch])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', overflow: 'hidden' }}>

      <Header
        wsStatus={wsStatus}
        onNewIncident={() => dispatch({ type: 'TOGGLE_FORM', payload: true })}
        onTogglePanel={() => setRightVisible(v => !v)}
        panelVisible={rightVisible}
      />

      <LiveTicker />

      {/* Three-column body */}
      <main style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>

        {/* Left — incident list */}
        <div style={{ width: 288, flexShrink: 0, overflow: 'hidden' }}>
          <IncidentPanel />
        </div>

        {/* Center — live map */}
        <div style={{ flex: 1, position: 'relative', overflow: 'hidden' }}>
          <LiveMap />
        </div>

        {/* Right — metrics / fleet (animated) */}
        <RightPanel visible={rightVisible} />
      </main>

      {/* New incident form modal */}
      <AnimatePresence>
        {state.showForm && <IncidentForm />}
      </AnimatePresence>

      {/* Toast notifications */}
      <Toaster
        position="bottom-right"
        toastOptions={{
          duration: 5000,
          style: {
            background: 'var(--bg-2)',
            color: 'var(--text-1)',
            border: '1px solid var(--b-2)',
            borderRadius: '8px',
            fontFamily: "'Space Mono', monospace",
            fontSize: '12px',
            boxShadow: '0 8px 32px rgba(0,0,0,0.5)',
          },
          success: {
            iconTheme: { primary: '#3ddc84', secondary: 'var(--bg-2)' },
          },
          error: {
            iconTheme: { primary: '#ff3d3d', secondary: 'var(--bg-2)' },
          },
        }}
      />
    </div>
  )
}

export default function App() {
  return (
    <StoreProvider>
      <AppInner />
    </StoreProvider>
  )
}

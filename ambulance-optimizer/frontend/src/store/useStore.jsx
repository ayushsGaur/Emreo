import { createContext, useContext, useReducer, useCallback } from 'react'

const Ctx = createContext(null)

const init = {
  incidents:   [],
  ambulances:  {},        // id → ambulance
  summary:     null,
  mlMetrics:   null,
  selectedId:  null,
  rightPanel:  'metrics', // 'metrics' | 'fleet'
  showForm:    false,
}

function reducer(s, { type, payload }) {
  switch (type) {
    case 'SET_INCIDENTS':  return { ...s, incidents: payload }
    case 'ADD_INCIDENT': {
      if (s.incidents.find(i => i.id === payload.id)) return s
      return { ...s, incidents: [{ ...payload, _new: true }, ...s.incidents] }
    }
    case 'UPDATE_INCIDENT':
      return { ...s, incidents: s.incidents.map(i => i.id === payload.id ? { ...i, ...payload } : i) }
    case 'SET_AMBULANCES':
      return { ...s, ambulances: Object.fromEntries(payload.map(a => [a.id, a])) }
    case 'UPDATE_AMB_LOC': {
      const { ambulance_id, lat, lng, heading, speed_kmh, status, timestamp } = payload
      const ex = s.ambulances[ambulance_id]
      if (!ex) return s
      return { ...s, ambulances: { ...s.ambulances, [ambulance_id]: { ...ex, latitude: lat, longitude: lng, heading_degrees: heading, speed_kmh, status: status || ex.status, last_location_update: timestamp } } }
    }
    case 'UPDATE_AMB_STATUS': {
      const ex = s.ambulances[payload.ambulance_id]
      if (!ex) return s
      return { ...s, ambulances: { ...s.ambulances, [payload.ambulance_id]: { ...ex, status: payload.new_status } } }
    }
    case 'SET_SUMMARY':    return { ...s, summary: payload }
    case 'SET_METRICS':    return { ...s, mlMetrics: payload }
    case 'SELECT':         return { ...s, selectedId: payload }
    case 'SET_PANEL':      return { ...s, rightPanel: payload }
    case 'TOGGLE_FORM':    return { ...s, showForm: payload }
    default: return s
  }
}

export function StoreProvider({ children }) {
  const [state, dispatch] = useReducer(reducer, init)
  return <Ctx.Provider value={{ state, dispatch }}>{children}</Ctx.Provider>
}

export function useStore() { return useContext(Ctx) }

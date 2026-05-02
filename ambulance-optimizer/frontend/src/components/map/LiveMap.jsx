import { useEffect, useRef } from 'react'
import { useStore } from '../../store/useStore.jsx'
import { SEV } from '../ui/primitives.jsx'

const CENTER = [30.9, 75.85]  // Ludhiana, Punjab
const ZOOM   = 13

// const TILES  = 'https://{s}.basemaps.cartocdn.com/dark_matter/{z}/{x}/{y}{r}.png'
const TILES  = 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png'
const ATTR = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
// const ATTR   = '©<a href="https://openstreetmap.org">OpenStreetMap</a> ©<a href="https://carto.com">CARTO</a>'

const AMB_STATUS_COLOR = {
  available:    '#3ddc84',
  dispatched:   '#38b6ff',
  on_scene:     '#f5c842',
  transporting: '#ff8c00',
  at_hospital:  '#ff3d3d',
  offline:      '#445566',
}

function makeAmbIcon(L, status) {
  const c = AMB_STATUS_COLOR[status] || '#445566'
  return L.divIcon({
    className: '',
    iconSize: [34, 34],
    iconAnchor: [17, 17],
    html: `<div style="
      width:34px;height:34px;display:flex;align-items:center;justify-content:center;position:relative;">
      <div style="
        width:26px;height:26px;background:${c};border:2px solid rgba(255,255,255,.85);
        border-radius:8px;display:flex;align-items:center;justify-content:center;
        font-size:14px;box-shadow:0 0 12px ${c}90;transition:all .3s;">🚑</div>
    </div>`,
  })
}

function makeIncIcon(L, severity) {
  const cfg = SEV[severity]
  const color = cfg?.color || '#8fa3b8'
  const isPulsing = severity === 'P1' || severity === 'P2'
  return L.divIcon({
    className: '',
    iconSize: [30, 30],
    iconAnchor: [15, 15],
    html: `<div style="width:30px;height:30px;display:flex;align-items:center;justify-content:center;position:relative;">
      ${isPulsing ? `<div style="position:absolute;inset:-4px;border-radius:50%;border:2px solid ${color};opacity:.5;animation:pulseRing 2s ease-out infinite;"></div>` : ''}
      <div style="width:16px;height:16px;background:${color};border:2.5px solid rgba(255,255,255,.9);border-radius:50%;box-shadow:0 0 10px ${color};z-index:1;"></div>
    </div>`,
  })
}

export default function LiveMap() {
  const { state, dispatch } = useStore()
  const containerRef  = useRef(null)
  const leafletRef    = useRef(null)   // { map, L }
  const ambMarkersRef = useRef({})
  const incMarkersRef = useRef({})
  const routeRef      = useRef(null)
  // const mapRef = useRef(null)

  /* ── Init map once ───────────────────────────── */
  useEffect(() => {
  if (!containerRef.current) return

  import('leaflet').then(({ default: L }) => {
    // remove old map if exists (React strict mode fix)
    if (leafletRef.current) {
      leafletRef.current.map.remove()
      leafletRef.current = null
    }

    const map = L.map(containerRef.current, {
      center: CENTER,
      zoom: ZOOM,
      zoomControl: true,
      attributionControl: true,
    })

    L.tileLayer(TILES, {
      attribution: ATTR,
      maxZoom: 19,
    }).addTo(map)

    leafletRef.current = { map, L }

    // inject pulse animation once
    if (!document.getElementById('map-pulse-style')) {
      const s = document.createElement('style')
      s.id = 'map-pulse-style'
      s.textContent = `
        @keyframes pulseRing {
          0% { transform: scale(1); opacity: .5 }
          100% { transform: scale(2.2); opacity: 0 }
        }
      `
      document.head.appendChild(s)
    }
  })

  return () => {
    if (leafletRef.current) {
      leafletRef.current.map.remove()
      leafletRef.current = null
    }
  }
}, [])


  // useEffect(() => {
  //   if (leafletRef.current) return

  //   import('leaflet').then(({ default: L }) => {
  //     // inject pulse keyframe
  //     if (!document.getElementById('map-pulse-style')) {
  //       const s = document.createElement('style')
  //       s.id = 'map-pulse-style'
  //       s.textContent = `@keyframes pulseRing{0%{transform:scale(1);opacity:.5}100%{transform:scale(2.2);opacity:0}}`
  //       document.head.appendChild(s)
  //     }


  //     // const map = L.map(containerRef.current, {
  //     //   center: CENTER, zoom: ZOOM,
  //     //   zoomControl: true, attributionControl: true,
  //     // })

  //     if (mapRef.current) return

  //     const map = L.map(containerRef.current, {
  //       center: CENTER,
  //       zoom: ZOOM,
  //       zoomControl: true,
  //       attributionControl: true,
  //     })

  //     mapRef.current = map

  //   return () => {
  //     if (mapRef.current) {
  //     mapRef.current.remove()
  //     mapRef.current = null
  //    }
  //  }

      

  //     L.tileLayer(TILES, { attribution: ATTR, maxZoom: 19 }).addTo(map)
  //     leafletRef.current = { map, L }
  //   })

  //   return () => {
  //     leafletRef.current?.map.remove()
  //     leafletRef.current = null
  //   }
  // }, []) // eslint-disable-line

  /* ── Sync ambulance markers ──────────────────── */
  useEffect(() => {
    if (!leafletRef.current) return
    const { map, L } = leafletRef.current
    const current = new Set(Object.keys(ambMarkersRef.current))

    Object.values(state.ambulances).forEach(amb => {
      if (!amb.latitude || !amb.longitude) return
      current.delete(amb.id)
      if (ambMarkersRef.current[amb.id]) {
        ambMarkersRef.current[amb.id]
          .setLatLng([amb.latitude, amb.longitude])
          .setIcon(makeAmbIcon(L, amb.status))
      } else {
        const m = L.marker([amb.latitude, amb.longitude], {
          icon: makeAmbIcon(L, amb.status),
          zIndexOffset: 200,
        })
          .bindPopup(`
            <div style="line-height:1.6">
              <div style="font-weight:700;font-size:13px;margin-bottom:4px">${amb.unit_number}</div>
              <div style="color:#8fa3b8">${amb.ambulance_type} · ${amb.status?.replace(/_/g,' ').toUpperCase()}</div>
              <div style="color:#445566;margin-top:3px">${amb.station_name}</div>
              ${amb.speed_kmh ? `<div style="color:#38b6ff;margin-top:3px">${Math.round(amb.speed_kmh)} km/h</div>` : ''}
            </div>
          `)
          .addTo(map)
        ambMarkersRef.current[amb.id] = m
      }
    })

    current.forEach(id => { ambMarkersRef.current[id]?.remove(); delete ambMarkersRef.current[id] })
  }, [state.ambulances])

  /* ── Sync incident markers ───────────────────── */
  useEffect(() => {
    if (!leafletRef.current) return
    const { map, L } = leafletRef.current
    const current = new Set(Object.keys(incMarkersRef.current))

    state.incidents
      .filter(i => i.status !== 'closed' && i.latitude && i.longitude)
      .forEach(inc => {
        current.delete(inc.id)
        const icon = makeIncIcon(L, inc.severity)
        if (incMarkersRef.current[inc.id]) {
          incMarkersRef.current[inc.id].setIcon(icon)
        } else {
          const m = L.marker([inc.latitude, inc.longitude], {
            icon,
            zIndexOffset: inc.severity === 'P1' ? 600 : inc.severity === 'P2' ? 400 : 200,
          })
            .bindPopup(`
              <div style="line-height:1.6;min-width:180px">
                <div style="font-weight:700;font-size:12px;margin-bottom:4px">${inc.severity || '?'} · ${inc.status?.replace(/_/g,' ').toUpperCase()}</div>
                <div style="color:#8fa3b8;margin-bottom:3px">${inc.complaint?.slice(0, 90)}</div>
                <div style="color:#445566">${inc.address}</div>
                ${inc.estimated_arrival_minutes ? `<div style="color:#38b6ff;margin-top:4px">ETA: ${Math.round(inc.estimated_arrival_minutes)} min</div>` : ''}
              </div>
            `)
            .on('click', () => dispatch({ type: 'SELECT', payload: inc.id }))
            .addTo(map)
          incMarkersRef.current[inc.id] = m
        }
      })

    current.forEach(id => { incMarkersRef.current[id]?.remove(); delete incMarkersRef.current[id] })
  }, [state.incidents, dispatch])

  /* ── Route polyline when incident selected ───── */
  useEffect(() => {
    if (!leafletRef.current) return
    const { map, L } = leafletRef.current

    routeRef.current?.remove()
    routeRef.current = null

    const inc = state.incidents.find(i => i.id === state.selectedId)
    if (!inc?.route_polyline) return

    try {
      const decoded = L.Polyline.fromEncoded
        ? L.Polyline.fromEncoded(inc.route_polyline).getLatLngs()
        : []
      if (!decoded.length) return
      const layer = L.polyline(decoded, {
        color: '#38b6ff', weight: 3, opacity: 0.9, dashArray: '10 5',
      }).addTo(map)
      routeRef.current = layer
      map.fitBounds(layer.getBounds(), { padding: [50, 50] })
    } catch { /* polyline decode failed */ }
  }, [state.selectedId, state.incidents])

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%' }}>
      <div ref={containerRef} style={{ width: '100%', height: '100%' }} />

      {/* Selected incident detail overlay */}
      <SelectedIncidentCard />

      {/* Legend */}
      <div style={{
        position: 'absolute', bottom: 22, left: 14, zIndex: 1000,
        background: 'rgba(6,10,14,.9)', border: '1px solid var(--b-2)',
        borderRadius: 'var(--r-lg)', padding: '11px 14px', backdropFilter: 'blur(8px)',
      }}>
        <div style={{ fontFamily: 'var(--font-mono)', fontSize: 9, letterSpacing: '.12em', textTransform: 'uppercase', color: 'var(--text-3)', marginBottom: 8 }}>Severity</div>
        {[['P1','var(--red)'],['P2','var(--orange)'],['P3','var(--yellow)'],['P4','var(--green)']].map(([s,c]) => (
          <div key={s} style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: 4 }}>
            <div style={{ width: 8, height: 8, borderRadius: '50%', background: c }} />
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-2)' }}>{s}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

function SelectedIncidentCard() {
  const { state, dispatch } = useStore()
  const inc = state.incidents.find(i => i.id === state.selectedId)
  if (!inc) return null

  return (
    <div className="animate-fade-up" style={{
      position: 'absolute', top: 14, left: 14, zIndex: 900,
      background: 'rgba(11,16,24,.95)', border: '1px solid var(--b-2)',
      borderRadius: 'var(--r-lg)', padding: 0,
      backdropFilter: 'blur(12px)', maxWidth: 320, width: '100%',
      boxShadow: '0 8px 40px rgba(0,0,0,.5)',
    }}>
      {/* Header */}
      <div style={{ padding: '10px 14px', borderBottom: '1px solid var(--b-1)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: 9, letterSpacing: '.12em', textTransform: 'uppercase', color: 'var(--text-3)' }}>Selected Incident</div>
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-2)' }}>#{inc.id?.slice(0, 8).toUpperCase()}</div>
        </div>
        <button onClick={() => dispatch({ type: 'SELECT', payload: null })} style={{
          width: 22, height: 22, borderRadius: '50%', background: 'var(--bg-3)', border: '1px solid var(--b-2)',
          color: 'var(--text-2)', fontSize: 13, display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>×</button>
      </div>

      {/* Body */}
      <div style={{ padding: '12px 14px', display: 'flex', flexDirection: 'column', gap: 8 }}>
        <div style={{ fontSize: 12, color: 'var(--text-1)', lineHeight: 1.5 }}>{inc.complaint}</div>
        {[
          ['Severity',  inc.severity ? <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, fontWeight: 700, color: { P1:'var(--red)',P2:'var(--orange)',P3:'var(--yellow)',P4:'var(--green)' }[inc.severity] }}>{inc.severity}</span> : '—'],
          ['Status',    <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--blue)' }}>{inc.status?.replace(/_/g,' ').toUpperCase()}</span>],
          ['Address',   <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-2)' }}>{inc.address}</span>],
          inc.estimated_arrival_minutes && ['ETA', <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, fontWeight: 700, color: 'var(--blue)' }}>{Math.round(inc.estimated_arrival_minutes)} min</span>],
          inc.severity_confidence && ['Confidence', <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-2)' }}>{(inc.severity_confidence * 100).toFixed(0)}%</span>],
        ].filter(Boolean).map(([label, val]) => (
          <div key={label} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12 }}>
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: 9, letterSpacing: '.08em', textTransform: 'uppercase', color: 'var(--text-3)', flexShrink: 0, paddingTop: 1 }}>{label}</span>
            {val}
          </div>
        ))}
        {inc.severity_flagged_for_review && (
          <div style={{ padding: '6px 9px', background: 'rgba(245,200,66,.08)', border: '1px solid rgba(245,200,66,.25)', borderRadius: 'var(--r-sm)', fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--yellow)' }}>
            ⚠ Flagged for manual review
          </div>
        )}
      </div>
    </div>
  )
}

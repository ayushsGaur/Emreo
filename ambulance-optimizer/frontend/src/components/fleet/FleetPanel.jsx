import { useStore } from '../../store/useStore.jsx'
import { StatusPill, EmptyState } from '../ui/primitives.jsx'

const AMB_COLOR = {
  available:    'var(--green)',
  dispatched:   'var(--blue)',
  on_scene:     'var(--yellow)',
  transporting: 'var(--orange)',
  at_hospital:  'var(--red)',
  offline:      'var(--text-3)',
}

export default function FleetPanel() {
  const { state } = useStore()
  const ambulances = Object.values(state.ambulances)

  const byStatus = ambulances.reduce((acc, a) => {
    acc[a.status] = (acc[a.status] || 0) + 1
    return acc
  }, {})

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflowY: 'auto' }}>
      <div style={{ padding: '12px 14px', display: 'flex', flexDirection: 'column', gap: 10 }}>

        {/* Summary grid */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6 }}>
          {Object.entries(byStatus).map(([status, count]) => (
            <div key={status} style={{ background: 'var(--bg-2)', border: '1px solid var(--b-1)', borderRadius: 'var(--r-md)', padding: '8px 10px' }}>
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: 18, fontWeight: 700, color: AMB_COLOR[status] || 'var(--text-2)', lineHeight: 1, marginBottom: 3 }}>{count}</div>
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: 9, letterSpacing: '.08em', textTransform: 'uppercase', color: 'var(--text-3)' }}>{status.replace(/_/g,' ')}</div>
            </div>
          ))}
        </div>

        <div style={{ height: 1, background: 'var(--b-1)', margin: '2px 0' }} />

        {/* Individual units */}
        {ambulances.length === 0 ? (
          <EmptyState icon="🚑" message="No ambulances registered" />
        ) : (
          ambulances
            .sort((a, b) => {
              const order = { available: 0, dispatched: 1, on_scene: 2, transporting: 3, at_hospital: 4, offline: 5 }
              return (order[a.status] ?? 9) - (order[b.status] ?? 9)
            })
            .map(amb => <AmbCard key={amb.id} amb={amb} />)
        )}
      </div>
    </div>
  )
}

function AmbCard({ amb }) {
  const color = AMB_COLOR[amb.status] || 'var(--text-3)'
  const isActive = amb.status !== 'offline' && amb.status !== 'available'

  return (
    <div style={{
      background: 'var(--bg-2)',
      border: `1px solid ${isActive ? color + '30' : 'var(--b-1)'}`,
      borderRadius: 'var(--r-md)',
      padding: '11px 12px',
      transition: 'border-color .2s',
    }}>
      {/* Top row */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 5 }}>
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 13, fontWeight: 700, color: 'var(--text-1)' }}>{amb.unit_number}</span>
        <span style={{
          fontFamily: 'var(--font-mono)', fontSize: 9, fontWeight: 700, letterSpacing: '.08em',
          color: amb.ambulance_type === 'ALS' ? 'var(--blue)' : 'var(--green)',
          background: amb.ambulance_type === 'ALS' ? 'var(--blue-d)' : 'var(--green-d)',
          border: `1px solid ${amb.ambulance_type === 'ALS' ? 'rgba(56,182,255,.25)' : 'rgba(61,220,132,.2)'}`,
          borderRadius: 3, padding: '1px 6px',
        }}>{amb.ambulance_type}</span>
      </div>

      <div style={{ fontSize: 11, color: 'var(--text-2)', marginBottom: 6 }}>{amb.station_name}</div>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <StatusPill status={amb.status} />
        {amb.latitude && (
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--text-3)' }}>
            {amb.latitude.toFixed(4)}, {amb.longitude.toFixed(4)}
          </span>
        )}
      </div>

      {amb.speed_kmh > 0 && (
        <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--blue)', marginTop: 4 }}>
          ↗ {Math.round(amb.speed_kmh)} km/h
        </div>
      )}
    </div>
  )
}

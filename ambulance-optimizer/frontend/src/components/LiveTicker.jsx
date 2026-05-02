import { useStore } from '../store/useStore.jsx'
import { SEV } from './ui/primitives.jsx'

export default function LiveTicker() {
  const { state } = useStore()

  const recentIncidents = state.incidents
    .filter(i => i.severity)
    .slice(0, 12)

  const items = recentIncidents.length > 0 ? recentIncidents : [
    { id: '1', severity: 'P1', complaint: 'Cardiac arrest — patient unresponsive', status: 'dispatched' },
    { id: '2', severity: 'P2', complaint: 'Severe chest pain, difficulty breathing', status: 'on_scene' },
    { id: '3', severity: 'P3', complaint: 'Fractured limb after road accident', status: 'dispatched' },
    { id: '4', severity: 'P4', complaint: 'Minor laceration, patient stable', status: 'received' },
  ]

  // duplicate for seamless loop
  const doubled = [...items, ...items]

  return (
    <div style={{
      height: 30, background: 'var(--bg-2)', borderBottom: '1px solid var(--b-1)',
      overflow: 'hidden', display: 'flex', alignItems: 'center', flexShrink: 0,
    }}>
      <div style={{
        fontFamily: 'var(--font-mono)', fontSize: 9, letterSpacing: '.12em',
        color: 'var(--red)', textTransform: 'uppercase',
        padding: '0 14px', height: '100%', display: 'flex', alignItems: 'center',
        borderRight: '1px solid rgba(255,61,61,.18)',
        background: 'rgba(255,61,61,.06)', flexShrink: 0,
      }}>
        ⚡ Live Feed
      </div>

      <div style={{ overflow: 'hidden', flex: 1 }}>
        <div style={{
          display: 'flex', whiteSpace: 'nowrap',
          animation: 'ticker 35s linear infinite',
        }}>
          {doubled.map((inc, i) => {
            const cfg = SEV[inc.severity]
            return (
              <div key={`${inc.id}-${i}`} style={{
                display: 'inline-flex', alignItems: 'center', gap: 8,
                padding: '0 28px', fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-2)',
              }}>
                <span style={{ width: 5, height: 5, borderRadius: '50%', background: cfg?.color || 'var(--text-3)', flexShrink: 0 }} />
                <span style={{ color: cfg?.color || 'var(--text-3)', fontWeight: 700 }}>{inc.severity}</span>
                <span>{inc.complaint?.slice(0, 55)}</span>
                <span style={{ color: 'var(--text-3)', margin: '0 4px' }}>·</span>
                <span style={{ color: 'var(--text-3)', textTransform: 'uppercase', fontSize: 9 }}>{inc.status?.replace(/_/g, ' ')}</span>
              </div>
            )
          })}
        </div>
      </div>

      <style>{`
        @keyframes ticker {
          0%   { transform: translateX(0); }
          100% { transform: translateX(-50%); }
        }
      `}</style>
    </div>
  )
}

import { AnimatePresence, motion } from 'framer-motion'
import { useStore } from '../store/useStore.jsx'
import { PanelHeader } from './ui/primitives.jsx'
import MLMetrics from './metrics/MLMetrics.jsx'
import FleetPanel from './fleet/FleetPanel.jsx'

export default function RightPanel({ visible }) {
  const { state, dispatch } = useStore()

  return (
    <AnimatePresence>
      {visible && (
        <motion.div
          key="right-panel"
          initial={{ width: 0, opacity: 0 }}
          animate={{ width: 272, opacity: 1 }}
          exit={{ width: 0, opacity: 0 }}
          transition={{ duration: 0.22, ease: 'easeInOut' }}
          style={{ flexShrink: 0, background: 'var(--bg-1)', borderLeft: '1px solid var(--b-1)', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}
        >
          <div style={{ width: 272, height: '100%', display: 'flex', flexDirection: 'column' }}>
            {/* Tabs */}
            <div style={{ display: 'flex', borderBottom: '1px solid var(--b-1)', flexShrink: 0 }}>
              {[
                { key: 'metrics', label: 'ML Monitor' },
                { key: 'fleet',   label: 'Fleet' },
              ].map(({ key, label }) => (
                <button
                  key={key}
                  onClick={() => dispatch({ type: 'SET_PANEL', payload: key })}
                  style={{
                    flex: 1, padding: '10px 0',
                    fontFamily: 'var(--font-mono)', fontSize: 9, fontWeight: 700,
                    letterSpacing: '.1em', textTransform: 'uppercase',
                    color: state.rightPanel === key ? 'var(--blue)' : 'var(--text-3)',
                    borderBottom: `2px solid ${state.rightPanel === key ? 'var(--blue)' : 'transparent'}`,
                    background: 'none', transition: 'all .15s',
                  }}
                >
                  {label}
                </button>
              ))}
            </div>

            {/* Content */}
            <div style={{ flex: 1, overflow: 'hidden', position: 'relative' }}>
              {state.rightPanel === 'metrics' && <MLMetrics />}
              {state.rightPanel === 'fleet'   && <FleetPanel />}
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}

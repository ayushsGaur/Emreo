import { useState, useCallback } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { formatDistanceToNow } from 'date-fns'
import toast from 'react-hot-toast'
import { useStore } from '../../store/useStore.jsx'
import { dispatchApi } from '../../services/api.js'
import { SeverityBadge, StatusPill, PanelHeader, EmptyState, Spinner } from '../ui/primitives.jsx'

const SEV_ORDER = { P1: 0, P2: 1, P3: 2, P4: 3 }

function sorted(incidents) {
  return [...incidents]
    .filter(i => i.status !== 'closed')
    .sort((a, b) => {
      const d = (SEV_ORDER[a.severity] ?? 4) - (SEV_ORDER[b.severity] ?? 4)
      return d !== 0 ? d : new Date(b.created_at) - new Date(a.created_at)
    })
}

export default function IncidentPanel() {
  const { state, dispatch } = useStore()
  const [loading, setLoading] = useState({})
  const list = sorted(state.incidents)

  const handleDispatch = useCallback(async (e, id) => {
    e.stopPropagation()
    setLoading(l => ({ ...l, [id]: true }))
    try {
      const result = await dispatchApi.trigger(id)
      dispatch({ type: 'UPDATE_INCIDENT', payload: {
        id, status: 'dispatched',
        assigned_ambulance_id: result.assigned_ambulance_id,
        estimated_arrival_minutes: result.estimated_arrival_minutes,
      }})
      toast.success(`${result.ambulance_type} dispatched · ETA ${Math.round(result.estimated_arrival_minutes)}min`, { icon: '🚑' })
    } catch (err) {
      toast.error(err.message || 'Dispatch failed')
    } finally {
      setLoading(l => ({ ...l, [id]: false }))
    }
  }, [dispatch])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', background: 'var(--bg-1)', borderRight: '1px solid var(--b-1)', overflow: 'hidden' }}>
      <PanelHeader title="Active Incidents" count={list.length} />

      <div style={{ flex: 1, overflowY: 'auto' }}>
        {list.length === 0 ? (
          <EmptyState icon="◎" message="No active incidents" />
        ) : (
          <AnimatePresence initial={false}>
            {list.map((inc, i) => (
              <motion.div
                key={inc.id}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, height: 0, overflow: 'hidden' }}
                transition={{ duration: 0.22, delay: i < 5 ? i * 0.04 : 0 }}
              >
                <IncidentRow
                  inc={inc}
                  selected={state.selectedId === inc.id}
                  dispatching={!!loading[inc.id]}
                  onSelect={() => dispatch({ type: 'SELECT', payload: inc.id })}
                  onDispatch={(e) => handleDispatch(e, inc.id)}
                />
              </motion.div>
            ))}
          </AnimatePresence>
        )}
      </div>
    </div>
  )
}

function IncidentRow({ inc, selected, dispatching, onSelect, onDispatch }) {
  const canDispatch = inc.status === 'received' || inc.status === 'dispatching'
  const timeAgo = inc.created_at ? formatDistanceToNow(new Date(inc.created_at), { addSuffix: true }) : ''

  return (
    <div
      onClick={onSelect}
      style={{
        padding: '11px 14px',
        borderBottom: '1px solid var(--b-1)',
        borderLeft: `3px solid ${selected ? 'var(--blue)' : inc.severity === 'P1' ? 'var(--red)' : inc.severity === 'P2' ? 'var(--orange)' : 'transparent'}`,
        background: selected ? 'var(--bg-3)' : 'transparent',
        cursor: 'pointer',
        transition: 'background .12s',
      }}
      onMouseEnter={e => { if (!selected) e.currentTarget.style.background = 'var(--bg-2)' }}
      onMouseLeave={e => { if (!selected) e.currentTarget.style.background = 'transparent' }}
    >
      {/* Row 1 — badge + time */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 5 }}>
        <SeverityBadge severity={inc.severity} size="xs" pulse={inc.severity === 'P1'} />
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--text-3)' }}>{timeAgo}</span>
      </div>

      {/* Complaint */}
      <div style={{
        fontSize: 12, color: 'var(--text-1)', lineHeight: 1.45, marginBottom: 4,
        display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden',
      }}>
        {inc.complaint}
      </div>

      {/* Address */}
      <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-3)', marginBottom: 8, overflow: 'hidden', whiteSpace: 'nowrap', textOverflow: 'ellipsis' }}>
        {inc.address}
      </div>

      {/* Row — status + action */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <StatusPill status={inc.status} />

        {canDispatch && (
          <button
            onClick={onDispatch}
            disabled={dispatching}
            style={{
              fontFamily: 'var(--font-mono)', fontSize: 9, fontWeight: 700,
              letterSpacing: '.08em', textTransform: 'uppercase',
              color: dispatching ? 'var(--text-3)' : 'var(--blue)',
              background: 'var(--blue-d)', border: '1px solid rgba(56,182,255,.28)',
              borderRadius: 4, padding: '3px 8px',
              display: 'inline-flex', alignItems: 'center', gap: 4,
              cursor: dispatching ? 'not-allowed' : 'pointer',
              opacity: dispatching ? 0.6 : 1, transition: 'all .15s',
            }}
          >
            {dispatching ? <Spinner size={9} /> : '⚡'}
            {dispatching ? 'Dispatching' : 'Dispatch'}
          </button>
        )}

        {inc.status === 'dispatched' && inc.estimated_arrival_minutes && (
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--blue)' }}>
            ETA {Math.round(inc.estimated_arrival_minutes)}m
          </span>
        )}
      </div>
    </div>
  )
}

import { useEffect } from 'react'
import {
  RadarChart, PolarGrid, PolarAngleAxis, Radar, ResponsiveContainer,
  BarChart, Bar, XAxis, YAxis, Tooltip, Cell,
} from 'recharts'
import { useStore } from '../../store/useStore.jsx'
import { dashboardApi } from '../../services/api.js'
import { KpiCard, EmptyState, Spinner } from '../ui/primitives.jsx'

const SEV_COLORS = { P1: '#ff3d3d', P2: '#ff8c00', P3: '#f5c842', P4: '#3ddc84' }

const ChartTip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  return (
    <div style={{ background: 'var(--bg-4)', border: '1px solid var(--b-2)', borderRadius: 7, padding: '8px 12px', fontFamily: 'var(--font-mono)', fontSize: 11 }}>
      <div style={{ color: 'var(--text-2)', marginBottom: 3 }}>{label}</div>
      {payload.map(p => (
        <div key={p.name} style={{ color: p.color || 'var(--text-1)' }}>{p.name}: {typeof p.value === 'number' ? p.value.toFixed(3) : p.value}</div>
      ))}
    </div>
  )
}

export default function MLMetrics() {
  const { state, dispatch } = useStore()
  const m = state.mlMetrics

  useEffect(() => {
    const load = () => dashboardApi.metrics().then(d => dispatch({ type: 'SET_METRICS', payload: d })).catch(console.error)
    load()
    const t = setInterval(load, 30000)
    return () => clearInterval(t)
  }, [dispatch])

  if (!m) return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', flexDirection: 'column', gap: 10 }}>
      <Spinner size={22} />
      <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-3)' }}>Loading metrics…</span>
    </div>
  )

  const isML     = m.mode === 'ml_model'
  const d30      = m.last_30_days || {}
  const bySev    = d30.by_severity || []
  const total    = d30.total_predictions || 0
  const flagRate = d30.flag_rate_pct || 0

  const radarData = bySev.map(r => ({ subject: r.priority, confidence: Math.round((r.avg_confidence || 0) * 100) }))
  const barData   = bySev.map(r => ({ name: r.priority, count: r.count, color: SEV_COLORS[r.priority] }))

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflowY: 'auto' }}>
      <div style={{ padding: '12px 14px', display: 'flex', flexDirection: 'column', gap: 12 }}>

        {/* Model status pill */}
        <div style={{
          display: 'flex', alignItems: 'center', gap: 10, padding: '9px 12px',
          background: isML ? 'rgba(61,220,132,.07)' : 'rgba(245,200,66,.07)',
          border: `1px solid ${isML ? 'rgba(61,220,132,.22)' : 'rgba(245,200,66,.22)'}`,
          borderRadius: 'var(--r-md)',
        }}>
          <span className={isML ? '' : 'blink'} style={{
            width: 8, height: 8, borderRadius: '50%', flexShrink: 0,
            background: isML ? 'var(--green)' : 'var(--yellow)',
            boxShadow: isML ? '0 0 8px var(--green)' : 'none',
          }} />
          <div>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, fontWeight: 700, color: isML ? 'var(--green)' : 'var(--yellow)', lineHeight: 1 }}>
              {isML ? 'XGBoost Active' : 'Rule-Based Fallback'}
            </div>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--text-3)', marginTop: 3 }}>{m.model_version}</div>
          </div>
        </div>

        {/* KPI mini grid */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 7 }}>
          <KpiCard label="Predictions 30d" value={total.toLocaleString()} />
          <KpiCard
            label="Flag Rate"
            value={`${flagRate.toFixed(1)}%`}
            color={flagRate > 15 ? 'var(--red)' : flagRate > 8 ? 'var(--orange)' : 'var(--green)'}
            sub="< 0.60 confidence"
          />
        </div>

        {/* Prediction volume bar chart */}
        {barData.length > 0 && (
          <div>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: 9, letterSpacing: '.12em', textTransform: 'uppercase', color: 'var(--text-3)', marginBottom: 10 }}>Predictions by severity</div>
            <ResponsiveContainer width="100%" height={110}>
              <BarChart data={barData} barSize={30} margin={{ left: -20, right: 0 }}>
                <XAxis dataKey="name" tick={{ fontFamily: 'var(--font-mono)', fontSize: 10, fill: '#8fa3b8' }} axisLine={false} tickLine={false} />
                <YAxis hide />
                <Tooltip content={<ChartTip />} cursor={{ fill: 'rgba(255,255,255,.04)' }} />
                <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                  {barData.map((e, i) => <Cell key={i} fill={e.color} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}

        {/* Confidence radar */}
        {radarData.length > 0 && (
          <div>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: 9, letterSpacing: '.12em', textTransform: 'uppercase', color: 'var(--text-3)', marginBottom: 6 }}>Avg confidence by class (%)</div>
            <ResponsiveContainer width="100%" height={170}>
              <RadarChart data={radarData} margin={{ top: 0, right: 20, bottom: 0, left: 20 }}>
                <PolarGrid stroke="rgba(255,255,255,.05)" />
                <PolarAngleAxis dataKey="subject" tick={{ fontFamily: 'var(--font-mono)', fontSize: 10, fill: '#8fa3b8' }} />
                <Radar dataKey="confidence" stroke="#38b6ff" fill="#38b6ff" fillOpacity={0.14} strokeWidth={1.5} />
              </RadarChart>
            </ResponsiveContainer>
          </div>
        )}

        {/* Safety threshold indicator */}
        <div style={{ background: 'var(--bg-2)', border: '1px solid var(--b-1)', borderRadius: 'var(--r-md)', padding: '11px 12px' }}>
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: 9, letterSpacing: '.12em', textTransform: 'uppercase', color: 'var(--text-3)', marginBottom: 8 }}>Safety threshold</div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-2)' }}>P1 recall ≥ 0.85</span>
            <span style={{
              fontFamily: 'var(--font-mono)', fontSize: 10, fontWeight: 700,
              color: isML ? 'var(--green)' : 'var(--yellow)',
              background: isML ? 'rgba(61,220,132,.1)' : 'rgba(245,200,66,.1)',
              border: `1px solid ${isML ? 'rgba(61,220,132,.3)' : 'rgba(245,200,66,.3)'}`,
              borderRadius: 4, padding: '2px 8px',
            }}>
              {isML ? '✓ VERIFIED' : '⚠ UNVERIFIED'}
            </span>
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-3)', lineHeight: 1.5 }}>
            {isML ? 'Model passed P1 recall check at training. Monitor monthly.' : 'Train the ML model to enable verified safety metrics.'}
          </div>
        </div>

        {/* Flagged incidents */}
        {d30.flagged_for_review > 0 && (
          <div style={{ padding: '9px 12px', background: 'rgba(255,61,61,.07)', border: '1px solid rgba(255,61,61,.2)', borderRadius: 'var(--r-md)' }}>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--red)', fontWeight: 700, marginBottom: 3 }}>
              {d30.flagged_for_review} flagged for review
            </div>
            <div style={{ fontSize: 11, color: 'var(--text-2)' }}>Low-confidence predictions need manual triage verification.</div>
          </div>
        )}

      </div>
    </div>
  )
}

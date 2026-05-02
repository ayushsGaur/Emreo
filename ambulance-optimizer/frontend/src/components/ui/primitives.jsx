import { clsx } from 'clsx'

/* ── Severity config ─────────────────────────────── */
export const SEV = {
  P1: { label: 'P1 · CRITICAL', color: 'var(--red)',    dim: 'var(--red-d)',    border: 'rgba(255,61,61,.35)',  pulse: 'pulse-red' },
  P2: { label: 'P2 · EMERGENT', color: 'var(--orange)', dim: 'var(--orange-d)', border: 'rgba(255,140,0,.35)', pulse: 'pulse-orange' },
  P3: { label: 'P3 · URGENT',   color: 'var(--yellow)', dim: 'var(--yellow-d)', border: 'rgba(245,200,66,.3)', pulse: '' },
  P4: { label: 'P4 · ROUTINE',  color: 'var(--green)',  dim: 'var(--green-d)',  border: 'rgba(61,220,132,.25)',pulse: '' },
}

export const STATUS_COLOR = {
  available:    'var(--green)',
  dispatched:   'var(--blue)',
  on_scene:     'var(--yellow)',
  transporting: 'var(--orange)',
  at_hospital:  'var(--red)',
  offline:      'var(--text-3)',
  received:     'var(--text-2)',
  dispatching:  'var(--blue)',
  closed:       'var(--text-3)',
}

/* ── SeverityBadge ───────────────────────────────── */
export function SeverityBadge({ severity, size = 'sm', pulse = false }) {
  const cfg = SEV[severity]
  if (!cfg) return <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-3)' }}>—</span>
  const pad = size === 'xs' ? '2px 6px' : size === 'md' ? '4px 10px' : '3px 8px'
  const fs  = size === 'xs' ? 10 : size === 'md' ? 12 : 11
  return (
    <span
      className={pulse ? cfg.pulse : ''}
      style={{
        display: 'inline-flex', alignItems: 'center', gap: 5,
        fontFamily: 'var(--font-mono)', fontSize: fs, fontWeight: 700, letterSpacing: '.05em',
        color: cfg.color, background: cfg.dim, border: `1px solid ${cfg.border}`,
        borderRadius: 'var(--r-xs)', padding: pad,
      }}
    >
      <span style={{ width: 5, height: 5, borderRadius: '50%', background: cfg.color, flexShrink: 0 }} />
      {cfg.label}
    </span>
  )
}

/* ── StatusPill ──────────────────────────────────── */
export function StatusPill({ status }) {
  const color = STATUS_COLOR[status] || 'var(--text-3)'
  const label = status?.replace(/_/g, ' ').toUpperCase() || '—'
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontFamily: 'var(--font-mono)', fontSize: 10, fontWeight: 700, color }}>
      <span style={{ width: 5, height: 5, borderRadius: '50%', background: color, flexShrink: 0 }} />
      {label}
    </span>
  )
}

/* ── KpiCard ─────────────────────────────────────── */
export function KpiCard({ label, value, unit, color, sub }) {
  return (
    <div style={{ background: 'var(--bg-3)', border: '1px solid var(--b-1)', borderRadius: 'var(--r-md)', padding: '12px 14px' }}>
      <div style={{ fontFamily: 'var(--font-mono)', fontSize: 9, letterSpacing: '.12em', textTransform: 'uppercase', color: 'var(--text-3)', marginBottom: 5 }}>{label}</div>
      <div style={{ fontFamily: 'var(--font-mono)', fontSize: 24, fontWeight: 700, color: color || 'var(--text-1)', lineHeight: 1, marginBottom: sub ? 3 : 0 }}>
        {value ?? '—'}
        {unit && <span style={{ fontSize: 12, fontWeight: 400, color: 'var(--text-2)', marginLeft: 4 }}>{unit}</span>}
      </div>
      {sub && <div style={{ fontSize: 11, color: 'var(--text-3)', marginTop: 2 }}>{sub}</div>}
    </div>
  )
}

/* ── PanelHeader ─────────────────────────────────── */
export function PanelHeader({ title, count, right }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 14px', borderBottom: '1px solid var(--b-1)', flexShrink: 0 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10, fontWeight: 700, letterSpacing: '.12em', textTransform: 'uppercase', color: 'var(--text-2)' }}>{title}</span>
        {count != null && (
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10, fontWeight: 700, color: 'var(--blue)', background: 'var(--blue-d)', border: '1px solid rgba(56,182,255,.25)', borderRadius: 20, padding: '1px 8px' }}>{count}</span>
        )}
      </div>
      {right}
    </div>
  )
}

/* ── Spinner ─────────────────────────────────────── */
export function Spinner({ size = 14, color = 'var(--blue)' }) {
  return (
    <span className="spin" style={{ display: 'inline-block', width: size, height: size, borderRadius: '50%', border: '2px solid transparent', borderTopColor: color }} />
  )
}

/* ── EmptyState ──────────────────────────────────── */
export function EmptyState({ icon = '◎', message }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8, padding: '40px 20px', color: 'var(--text-3)' }}>
      <span style={{ fontSize: 26, opacity: 0.35 }}>{icon}</span>
      <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11 }}>{message}</span>
    </div>
  )
}

/* ── Btn ─────────────────────────────────────────── */
export function Btn({ children, variant = 'ghost', onClick, disabled, style: s }) {
  const variants = {
    ghost:   { background: 'var(--bg-3)', border: '1px solid var(--b-2)', color: 'var(--text-2)' },
    primary: { background: 'var(--red)',  border: '1px solid var(--red)',  color: '#fff', boxShadow: '0 0 14px rgba(255,61,61,.3)' },
    blue:    { background: 'var(--blue-d)', border: '1px solid rgba(56,182,255,.3)', color: 'var(--blue)' },
    active:  { background: 'var(--blue-d)', border: '1px solid var(--blue)', color: 'var(--blue)' },
  }
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      style={{
        fontFamily: 'var(--font-mono)', fontSize: 10, fontWeight: 700,
        letterSpacing: '.08em', textTransform: 'uppercase',
        borderRadius: 'var(--r-md)', padding: '6px 12px',
        display: 'inline-flex', alignItems: 'center', gap: 5,
        opacity: disabled ? 0.45 : 1,
        cursor: disabled ? 'not-allowed' : 'pointer',
        ...variants[variant], ...s,
      }}
    >
      {children}
    </button>
  )
}

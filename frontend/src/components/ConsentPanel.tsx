import { useEffect, useState } from 'react'
import type { ConsentPresentation } from '../models/types'

type Props = {
  presentation: ConsentPresentation
  busy: boolean
  onDecision: (decision: 'APPROVE' | 'REJECT', method: 'MOCK_BIOMETRIC' | 'MOCK_PIN') => void
  onClose: () => void
}

function formatMoney(value: string, fixed = false) {
  const [whole = '0', fraction] = value.split('.')
  const groupedWhole = whole.replace(/\B(?=(\d{3})+(?!\d))/g, ',')
  if (fraction !== undefined || fixed) return `${groupedWhole}.${(fraction ?? '').padEnd(2, '0')}`
  return groupedWhole
}

export function ConsentPanel({ presentation, busy, onDecision, onClose }: Props) {
  const [seconds, setSeconds] = useState(() => Math.max(0, Math.floor((Date.parse(presentation.expires_at) - Date.now()) / 1000)))
  const [method, setMethod] = useState<'MOCK_BIOMETRIC' | 'MOCK_PIN'>('MOCK_BIOMETRIC')

  useEffect(() => {
    const timer = window.setInterval(() => setSeconds(Math.max(0, Math.floor((Date.parse(presentation.expires_at) - Date.now()) / 1000))), 1000)
    return () => window.clearInterval(timer)
  }, [presentation.expires_at])

  return (
    <div className="modal-backdrop" role="presentation">
      <section className="consent-panel" role="dialog" aria-modal="true" aria-labelledby="consent-title">
        <div className="panel-topline"><span className="eyebrow">CUSTOMER ACTION · SIMULATED</span><button className="icon-button" onClick={onClose} aria-label="Close consent panel">×</button></div>
        <h2 id="consent-title">Review and confirm</h2>
        <p className="muted">This mock consent is bound to the exact validated payment below.</p>
        <dl className="consent-details">
          <div><dt>From account</dt><dd>{presentation.from_account}</dd></div>
          <div><dt>Beneficiary</dt><dd>{presentation.beneficiary}</dd></div>
          <div><dt>Amount</dt><dd className="money">{presentation.currency} {formatMoney(presentation.amount)}</dd></div>
          <div><dt>Fee</dt><dd>{presentation.currency} {formatMoney(presentation.fee, true)}</dd></div>
          <div><dt>Execution date</dt><dd>{presentation.execution_date}</dd></div>
        </dl>
        <div className="challenge-meta"><span>Challenge <code>{presentation.challenge_id}</code></span><span>Expires in <b>{Math.floor(seconds / 60)}:{String(seconds % 60).padStart(2, '0')}</b></span></div>
        <label className="select-label" htmlFor="mock-auth">Mock approval method</label>
        <select id="mock-auth" value={method} onChange={(event) => setMethod(event.target.value as typeof method)}>
          <option value="MOCK_BIOMETRIC">Approve with mock biometric</option>
          <option value="MOCK_PIN">Enter mock PIN</option>
        </select>
        <p className="simulation-note">Simulated only — no real biometric, PIN, banking credential, or payment is used.</p>
        <div className="consent-actions">
          <button className="button quiet" onClick={() => onDecision('REJECT', method)} disabled={busy}>Reject</button>
          <button className="button primary" onClick={() => onDecision('APPROVE', method)} disabled={busy || seconds === 0}>
            {busy ? 'Submitting…' : method === 'MOCK_PIN' ? 'Approve with mock PIN' : 'Approve with mock biometric'}
          </button>
        </div>
        <button className="text-button" onClick={onClose}>Modify request instead</button>
      </section>
    </div>
  )
}

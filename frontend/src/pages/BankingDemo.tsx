import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { ConsentPanel } from '../components/ConsentPanel'
import { StatusBadge } from '../components/StatusBadge'
import { api } from '../services/api'
import type { ConsentPresentation, TraceEntry, Workflow, WorkItem } from '../models/types'

const examples = [
  'Check my balance.',
  'Transfer THB 10,000 from my savings account to Somchai.',
  'Check my balance, transfer THB 10,000 to Somchai, then pay my electricity bill.',
  "What is today's transfer limit?",
]

const modes = [
  ['normal', 'Normal execution'],
  ['deny_policy', 'Deny pre-agent policy'],
  ['require_consent', 'Require consent'],
  ['reject_consent', 'Reject consent'],
  ['expire_consent', 'Expire consent'],
  ['bank_failure', 'Bank commit failure'],
  ['unknown_completed', 'Unknown → completed'],
  ['unknown_failed', 'Unknown → failed'],
  ['delay_events', 'Delay event delivery'],
  ['duplicate_events', 'Duplicate event delivery'],
]

function time(value: string) {
  return new Date(value).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

function formatMoney(value: string | undefined, fixed = false) {
  const [whole = '0', fraction] = (value ?? '0').split('.')
  const groupedWhole = whole.replace(/\B(?=(\d{3})+(?!\d))/g, ',')
  if (fraction !== undefined || fixed) return `${groupedWhole}.${(fraction ?? '').padEnd(2, '0')}`
  return groupedWhole
}

export function BankingDemo() {
  const [workflow, setWorkflow] = useState<Workflow | null>(null)
  const [messages, setMessages] = useState<{ text: string; role: 'customer' | 'assistant'; time: string }[]>([
    { text: 'Welcome. I can help with your accounts using synthetic demo data.', role: 'assistant', time: time(new Date().toISOString()) },
  ])
  const [draft, setDraft] = useState('')
  const [trace, setTrace] = useState<TraceEntry[]>([])
  const [traceFilter, setTraceFilter] = useState('all')
  const [selectedWorkItem, setSelectedWorkItem] = useState('all')
  const [componentFilter, setComponentFilter] = useState('all')
  const [consent, setConsent] = useState<ConsentPresentation | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [mode, setMode] = useState('normal')
  const [developerOpen, setDeveloperOpen] = useState(false)
  const [chatOpen, setChatOpen] = useState(true)
  const [workflowOpen, setWorkflowOpen] = useState(true)
  const [traceOpen, setTraceOpen] = useState(true)
  const seenEventIds = useRef(new Set<string>())
  const didRestore = useRef(false)

  useEffect(() => {
    if (didRestore.current) return
    didRestore.current = true
    void api.getConversationWorkflows().then(({ workflows }) => {
      const latest = workflows[0]
      if (!latest) return
      setWorkflow(latest)
      if (latest.original_message) {
        setMessages((current) => [
          ...current,
          { text: latest.original_message!, role: 'customer', time: time(latest.created_at) },
          {
            text: `Restored workflow ${latest.workflow_id} from durable demo state.`,
            role: 'assistant',
            time: time(latest.created_at),
          },
        ])
      }
    }).catch(() => setError('Could not restore the latest synthetic workflow'))
  }, [])

  const refresh = useCallback(async (id: string) => {
    try {
      const [latest, traceResult] = await Promise.all([api.getWorkflow(id), api.getTrace(id)])
      setWorkflow(latest)
      setTrace(traceResult.entries)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Could not refresh workflow')
    }
  }, [])

  useEffect(() => {
    if (!workflow) return
    const source = new EventSource(api.eventsUrl(workflow.workflow_id))
    source.addEventListener('workflow', (message) => {
      const event = JSON.parse((message as MessageEvent).data) as TraceEntry & { message?: string }
      if (seenEventIds.current.has(event.event_id)) return
      seenEventIds.current.add(event.event_id)
      if (event.response_status === 'UNKNOWN') {
        setMessages((current) => [...current, {
          text: `Checking transaction status for ${event.work_item_id ?? 'this work item'}…`,
          role: 'assistant', time: time(event.occurred_at),
        }])
      }
      void refresh(workflow.workflow_id)
    })
    const interval = window.setInterval(() => void refresh(workflow.workflow_id), 2000)
    return () => {
      source.close()
      window.clearInterval(interval)
    }
  }, [workflow?.workflow_id, refresh])

  const visibleTrace = useMemo(() => trace.filter((entry) => {
    const matchesItem = selectedWorkItem === 'all' || entry.work_item_id === selectedWorkItem
    const matchesComponent = componentFilter === 'all' || entry.caller === componentFilter || entry.executor === componentFilter
    const matchesKind = traceFilter === 'all'
      || (traceFilter === 'events' && entry.event_name.toLowerCase().includes('workitem'))
      || (traceFilter === 'errors' && ['FAILED', 'UNKNOWN', 'CONSENT_REJECTED', 'CONSENT_EXPIRED'].includes(entry.response_status))
      || (traceFilter === 'calls' && entry.event_name.includes('started'))
      || (traceFilter === 'returns' && !entry.event_name.includes('started'))
    return matchesItem && matchesComponent && matchesKind
  }), [trace, selectedWorkItem, componentFilter, traceFilter])

  async function submit(message = draft) {
    const value = message.trim()
    if (!value || busy) return
    setBusy(true)
    setError('')
    setMessages((current) => [...current, { text: value, role: 'customer', time: time(new Date().toISOString()) }])
    setDraft('')
    try {
      const result = await api.submitMessage(value)
      setWorkflow(result.workflow)
      setMessages((current) => [...current, {
        text: `Request accepted into workflow ${result.workflowId}. This does not mean a payment has completed.`,
        role: 'assistant', time: time(new Date().toISOString()),
      }])
      const entries = await api.getTrace(result.workflowId)
      setTrace(entries.entries)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Could not submit message')
    } finally {
      setBusy(false)
    }
  }

  async function openConsent(item: WorkItem) {
    if (!item.confirmation_challenge_id) return
    try {
      setConsent(await api.getPresentation(item.confirmation_challenge_id))
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Could not open consent')
    }
  }

  async function decideConsent(decision: 'APPROVE' | 'REJECT', method: 'MOCK_BIOMETRIC' | 'MOCK_PIN') {
    if (!consent || !workflow) return
    setBusy(true)
    try {
      await api.decideConsent(consent, decision, method)
      setMessages((current) => [...current, {
        text: 'CONSENT_RECEIVED — the structured consent command was accepted; transaction status follows asynchronously.',
        role: 'assistant', time: time(new Date().toISOString()),
      }])
      setConsent(null)
      await refresh(workflow.workflow_id)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Consent decision failed')
    } finally {
      setBusy(false)
    }
  }

  async function updateMode(next: string) {
    setMode(next)
    try {
      await api.setMode(next)
    } catch {
      setError('Developer control could not reach the mock API')
    }
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <div className="brand">
          <div className="brand-mark">N</div>
          <div><strong>northstar</strong><span>CONVERSATIONAL BANKING · ARCHITECTURE DEMO</span></div>
        </div>
        <div className="topbar-actions">
          <span className="data-label"><i /> SYNTHETIC DATA</span>
          <button className="button subtle" onClick={() => setDeveloperOpen((open) => !open)} aria-expanded={developerOpen}>Developer controls</button>
        </div>
      </header>
      <div className="demo-banner"><span>DEVELOPER PROTOTYPE</span> All customers, accounts, balances and bank references are synthetic mock data.</div>
      {developerOpen && (
        <section className="developer-panel" aria-label="Developer controls">
          <div><strong>Scenario controls</strong><span>Changes apply to the next customer request.</span></div>
          <label htmlFor="scenario-mode">Execution mode</label>
          <select id="scenario-mode" value={mode} onChange={(event) => void updateMode(event.target.value)}>
            {modes.map(([value, label]) => <option value={value} key={value}>{label}</option>)}
          </select>
          <button className="text-button" onClick={() => void updateMode('normal')}>Reset to normal</button>
        </section>
      )}
      {error && <div className="error-banner" role="alert">{error}<button onClick={() => setError('')}>Dismiss</button></div>}

      <section className="welcome-row">
        <div><p className="eyebrow">YOUR FINANCIAL LIFE, IN CONVERSATION</p><h1>Good evening, Alex.</h1><p className="muted">Ask for a balance, plan a transfer, or explore how a request moves through the system.</p></div>
        <div className="account-pill"><span className="account-avatar">AS</span><span><b>Alex Somchai</b><small>Demo customer · SYN-001</small></span><span className="pill-tag">MOCK</span></div>
      </section>

      <section className="workspace" aria-label="Banking architecture demo">
        <section className={`workspace-panel conversation-panel ${chatOpen ? '' : 'collapsed'}`}>
          <div className="panel-heading">
            <div><span className="panel-icon blue-icon">◌</span><div><h2>Conversation</h2><p>Natural language → Orchestrator</p></div></div>
            <button className="icon-button" aria-label="Collapse conversation pane" onClick={() => setChatOpen((open) => !open)}>{chatOpen ? '−' : '+'}</button>
          </div>
          {chatOpen && <>
            <div className="message-list" aria-live="polite">
              {messages.map((message, index) => <div key={`${message.time}-${index}`} className={`message ${message.role}`}>
                <div className="message-avatar">{message.role === 'customer' ? 'AS' : 'N'}</div>
                <div className="message-body"><div className="message-meta"><b>{message.role === 'customer' ? 'You' : 'Northstar'}</b><time>{message.time}</time></div><p>{message.text}</p></div>
              </div>)}
            </div>
            <div className="sample-prompts">
              <span className="eyebrow">TRY A SAMPLE</span>
              {examples.map((example) => <button key={example} onClick={() => void submit(example)} disabled={busy}>{example}</button>)}
            </div>
            <form className="composer" onSubmit={(event) => { event.preventDefault(); void submit() }}>
              <label htmlFor="chat-input" className="sr-only">Message Northstar</label>
              <textarea id="chat-input" placeholder="Ask about your accounts…" value={draft} onChange={(event) => setDraft(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); void submit() } }} />
              <div><span>Enter to send · Shift + Enter for new line</span><button className="send-button" aria-label="Send message" disabled={busy || !draft.trim()}>↑</button></div>
            </form>
          </>}
        </section>

        <section className={`workspace-panel workflow-panel ${workflowOpen ? '' : 'collapsed'}`}>
          <div className="panel-heading">
            <div><span className="panel-icon purple-icon">⌘</span><div><h2>Work-item status</h2><p>One durable request workflow · N work items</p></div></div>
            <button className="icon-button" aria-label="Collapse work-item status pane" onClick={() => setWorkflowOpen((open) => !open)}>{workflowOpen ? '−' : '+'}</button>
          </div>
          {workflowOpen && <div className="workflow-content">
            {workflow ? <>
              <div className="workflow-summary">
                <div><span className="eyebrow">REQUEST WORKFLOW</span><strong>{workflow.workflow_id}</strong></div>
                <StatusBadge status={workflow.request_status} />
                <small>{workflow.work_items.length} work items · correlation {workflow.correlation_id}</small>
              </div>
              <div className="work-items">
                {workflow.work_items.map((item) => <article className={`work-card ${item.status === 'AWAITING_CONSENT' ? 'needs-action' : ''}`} key={item.work_item_id}>
                  <div className="work-card-top"><span className="work-id">{item.work_item_id}</span><StatusBadge status={item.status} /></div>
                  <h3>{item.intent.replaceAll('_', ' ')}</h3>
                  <div className="work-type">{item.type} · agent {item.agent_id ?? '—'}</div>
                  <div className="work-facts">
                    <span><small>POLICY</small>{item.policy_status}</span>
                    <span><small>CONSENT</small>{item.consent_status}</span>
                    <span><small>TRANSACTION</small>{item.transaction_status}</span>
                  </div>
                  {item.dependencies.length > 0 && <p className="dependency">↳ Depends on {item.dependencies.join(', ')} completion</p>}
                  {item.result && <p className="result-text">{item.result}</p>}
                  {item.status === 'AWAITING_CONSENT' && <button className="button consent-trigger" onClick={() => void openConsent(item)}>Review consent for {item.prepared_payload?.currency} {formatMoney(item.prepared_payload?.amount)}</button>}
                  <footer>Updated {time(item.last_update)}{item.bank_reference && <span> · Synthetic ref {item.bank_reference}</span>}</footer>
                </article>)}
              </div>
            </> : <div className="empty-state"><span className="empty-icon">⌘</span><h3>Your workflow appears here</h3><p>Send a request to see one durable workflow with its work items, dependencies and customer actions.</p></div>}
          </div>}
        </section>

        <section className={`workspace-panel trace-panel ${traceOpen ? '' : 'collapsed'}`}>
          <div className="panel-heading">
            <div><span className="panel-icon green-icon">↗</span><div><h2>Technical trace</h2><p>Callers · executors · workflow events</p></div></div>
            <button className="icon-button" aria-label="Collapse technical trace pane" onClick={() => setTraceOpen((open) => !open)}>{traceOpen ? '−' : '+'}</button>
          </div>
          {traceOpen && <>
            <div className="trace-filters">
              <label><span className="sr-only">Filter by work item</span><select aria-label="Filter by work item" value={selectedWorkItem} onChange={(event) => setSelectedWorkItem(event.target.value)}>
                <option value="all">All work items</option>
                {workflow?.work_items.map((item) => <option key={item.work_item_id}>{item.work_item_id}</option>)}
              </select></label>
              <label><span className="sr-only">Filter by component</span><select aria-label="Filter by component" value={componentFilter} onChange={(event) => setComponentFilter(event.target.value)}>
                <option value="all">All components</option>
                {[...new Set(trace.flatMap((entry) => [entry.caller, entry.executor]))].map((component) => <option key={component}>{component}</option>)}
              </select></label>
              <label><span className="sr-only">Filter trace type</span><select aria-label="Filter trace type" value={traceFilter} onChange={(event) => setTraceFilter(event.target.value)}>
                <option value="all">All activity</option><option value="calls">Calls</option><option value="returns">Returns</option><option value="events">Events</option><option value="errors">Errors</option>
              </select></label>
            </div>
            <div className="trace-list">
              {visibleTrace.length ? visibleTrace.map((entry) => <article className="trace-entry" key={entry.event_id}>
                <span className={`trace-dot ${entry.response_status === 'FAILED' || entry.response_status === 'UNKNOWN' ? 'trace-error' : ''}`} />
                <div className="trace-content">
                  <div className="trace-title"><b>{entry.event_name}</b><time>{time(entry.occurred_at)}</time></div>
                  <p><span>{entry.caller}</span><i>→</i><span>{entry.executor}</span></p>
                  <code>{entry.contract}</code>
                  <small>{entry.workflow_id}{entry.work_item_id ? ` · ${entry.work_item_id}` : ''}</small>
                  <StatusBadge status={entry.response_status} />
                </div>
              </article>) : <div className="empty-trace">{workflow ? 'No activity matches the selected filters.' : 'Submit a request to inspect the service trace.'}</div>}
            </div>
            <div className="state-owner"><span>AUTHORITATIVE STATE</span><b>Request Workflow</b><small>Conversation Manager owns the customer-facing projection · Bank owns transaction outcome</small></div>
          </>}
        </section>
      </section>
      <footer className="page-footer"><span>Northstar synthetic banking sandbox</span><span>AI prepares · customer confirms · deterministic worker executes</span><a href="http://localhost:8000/docs" target="_blank" rel="noreferrer">API contracts ↗</a></footer>

      {consent && <ConsentPanel presentation={consent} busy={busy} onDecision={(decision, method) => void decideConsent(decision, method)} onClose={() => setConsent(null)} />}
    </main>
  )
}

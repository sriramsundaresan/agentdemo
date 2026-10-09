import type { ConsentPresentation, TraceEntry, Workflow } from '../models/types'

const base = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'
const conversationId = 'CONV-SYNTHETIC-001'

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${base}${path}`, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...options?.headers },
  })
  if (!response.ok) {
    const body = await response.json().catch(() => ({ message: response.statusText }))
    throw new Error(body.detail ?? body.message ?? body.code ?? `Request failed (${response.status})`)
  }
  return response.json() as Promise<T>
}

export const api = {
  async submitMessage(message: string) {
    return request<{ workflow: Workflow; workflowId: string }>('/api/conversations/CONV-SYNTHETIC-001/messages', {
      method: 'POST',
      body: JSON.stringify({ message, conversation_id: conversationId }),
    })
  },
  getWorkflow(id: string) {
    return request<Workflow>(`/api/conversations/${conversationId}/workflows/${id}`)
  },
  getConversationWorkflows() {
    return request<{ workflows: Workflow[] }>(`/api/conversations/${conversationId}/workflows`)
  },
  getTrace(id: string) {
    return request<{ entries: TraceEntry[] }>(`/api/conversations/${conversationId}/workflows/${id}/trace`)
  },
  getPresentation(id: string) {
    return request<ConsentPresentation>(`/api/confirmation-challenges/${id}/presentation`)
  },
  decideConsent(challenge: ConsentPresentation, decision: 'APPROVE' | 'REJECT', method: 'MOCK_BIOMETRIC' | 'MOCK_PIN') {
    return request<{ acknowledgement: string }>(`/api/confirmation-challenges/${challenge.challenge_id}/decision`, {
      method: 'POST',
      body: JSON.stringify({
        challenge_id: challenge.challenge_id,
        conversation_id: conversationId,
        payload_hash: challenge.payload_hash,
        decision,
        evidence_method: method,
        evidence: 'synthetic-demo-evidence',
        command_id: `CMD-${crypto.randomUUID()}`,
      }),
    })
  },
  setMode(mode: string) {
    return request<{ mode: string }>('/api/developer/controls', {
      method: 'POST',
      body: JSON.stringify({ mode }),
    })
  },
  eventsUrl(id: string) {
    return `${base}/api/conversations/${conversationId}/workflows/${id}/events`
  },
}

export type WorkItem = {
  work_item_id: string
  intent: string
  type: 'read-only' | 'knowledge' | 'financial'
  status: string
  dependencies: string[]
  agent_id?: string
  policy_status: string
  consent_status: string
  transaction_status: string
  last_update: string
  prepared_payload?: {
    from_account?: string
    beneficiary?: string
    amount?: string
    currency?: string
    fee?: string
    execution_date?: string
    balance?: { balance: string; currency: string }
    [key: string]: unknown
  }
  confirmation_challenge_id?: string
  payload_hash?: string
  bank_reference?: string
  result?: string
  idempotency_key?: string
}

export type Workflow = {
  workflow_id: string
  conversation_id: string
  request_status: string
  work_items: WorkItem[]
  created_at: string
  correlation_id: string
  original_message?: string
}

export type TraceEntry = {
  event_id: string
  event_name: string
  caller: string
  executor: string
  contract: string
  correlation_id: string
  workflow_id: string
  work_item_id?: string
  request_status: string
  response_status: string
  occurred_at: string
}

export type ConsentPresentation = {
  challenge_id: string
  work_item_id: string
  from_account: string
  beneficiary: string
  amount: string
  currency: string
  fee: string
  execution_date: string
  expires_at: string
  payload_hash: string
  synthetic: boolean
}

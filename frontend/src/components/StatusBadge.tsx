export function StatusBadge({ status }: { status: string }) {
  const tone = status.includes('COMPLETED') || status === 'READY' || status === 'CONFIRMED'
    ? 'good'
    : status.includes('AWAITING') || status.includes('BLOCKED') || status.includes('POLICY')
      ? 'pending'
      : status.includes('FAILED') || status.includes('UNKNOWN') || status.includes('REJECT') || status.includes('EXPIRED')
        ? 'bad'
        : 'active'
  return <span className={`status-badge ${tone}`} data-testid="status-badge">{status.replaceAll('_', ' ')}</span>
}

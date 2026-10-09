import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { StatusBadge } from './StatusBadge'

describe('StatusBadge', () => {
  it('renders semantic workflow status without presenting a fabricated percentage', () => {
    render(<StatusBadge status="AWAITING_CONSENT" />)
    expect(screen.getByTestId('status-badge')).toHaveTextContent('AWAITING CONSENT')
    expect(screen.queryByText(/%/)).not.toBeInTheDocument()
  })
})

import { expect, test } from '@playwright/test'

test('submits a multi-intent request and receives two separate consent challenges', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: /check my balance, transfer thb 10,000 to somchai, then pay my electricity bill/i }).click()

  await expect(page.getByText(/one durable request workflow/i)).toBeVisible()
  await expect(page.locator('.work-id')).toHaveText(['WI-1', 'WI-2', 'WI-3'])
  await expect(page.locator('.work-card .status-badge').filter({ hasText: 'BLOCKED BY DEPENDENCY' })).toBeVisible()
  const workflowId = await page.locator('.workflow-summary strong').textContent()
  await page.reload()
  await expect(page.locator('.workflow-summary strong')).toHaveText(workflowId!)

  await page.getByRole('button', { name: /review consent for thb 10,000/i }).click()
  await expect(page.getByRole('dialog')).toContainText('Simulated only')
  const transferChallenge = await page.locator('.challenge-meta code').textContent()
  await page.getByRole('button', { name: 'Approve with mock biometric' }).click()
  await expect(page.locator('.message.assistant p').filter({ hasText: 'CONSENT_RECEIVED' })).toBeVisible()

  await expect(page.getByRole('button', { name: /review consent for thb 2,500/i })).toBeVisible({ timeout: 10_000 })
  await page.getByRole('button', { name: /review consent for thb 2,500/i }).click()
  const billChallenge = await page.locator('.challenge-meta code').textContent()
  expect(billChallenge).not.toBe(transferChallenge)
  await page.getByRole('button', { name: 'Approve with mock biometric' }).click()
  await expect(page.getByText(/MOCK-TXN-/).first()).toBeVisible({ timeout: 10_000 })
})

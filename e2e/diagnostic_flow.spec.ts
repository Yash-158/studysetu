// M4 GATE: fresh topic -> generate -> review queue -> approve-all -> Yash's probe (5 items) ->
// review screen shows stored reasoning -> mastery rows updated. Run against a REAL configured
// provider chain (config/ai.yaml item_bank: [claude_sonnet, gemini_flash]) - this session's
// ANTHROPIC_API_KEY is deliberately unconfigured, so every run of this spec also exercises a real
// claude_sonnet -> gemini_flash failover (see docs/MEMORY.md), not just the mocked pytest coverage
// in apps/api/tests/test_ai_gateway.py.
// Run `uv run scripts/seed_demo.py` against a fresh DB first (see README.md "Determinism"). Uses a
// per-run unique topic name so the spec is re-runnable against the same persistent DB.
import { test, expect } from '@playwright/test'

const INSTITUTION_SLUG = 'gls-demo'
const ANVI = { identifier: 'anvi@gls-demo.test', password: 'Passw0rd!2' }
const YASH = { identifier: '21BCE001', password: 'Passw0rd!3' }
const RUN_ID = Date.now().toString().slice(-6)
const TOPIC_TITLE = `Edge Detection ${RUN_ID}`

async function login(page: import('@playwright/test').Page, identifier: string, password: string) {
  await page.goto('/login')
  await page.getByLabel('Institution code').fill(INSTITUTION_SLUG)
  await page.getByLabel('Roll number or email').fill(identifier)
  await page.getByLabel('Password', { exact: true }).fill(password)
  await page.getByRole('button', { name: 'Log in' }).click()
}

test.describe.serial('M4 GATE: fresh topic -> generate -> approve-all -> Yash\'s probe -> review -> mastery', () => {
  test('Anvi and Yash activate once (seed accounts, first run only)', async ({ page }) => {
    for (const { identifier, code, password } of [
      { identifier: ANVI.identifier, code: '22222222', password: ANVI.password },
      { identifier: YASH.identifier, code: '33333333', password: YASH.password },
    ]) {
      await page.goto('/activate')
      await page.getByLabel('Institution code').fill(INSTITUTION_SLUG)
      await page.getByLabel('Roll number or email').fill(identifier)
      await page.getByLabel('Activation code').fill(code)
      await page.getByLabel('New password').fill(password)
      await page.getByLabel('Confirm password').fill(password)
      await page.getByRole('button', { name: 'Activate' }).click()
      await page.waitForTimeout(300) // already-active on repeat runs shows an error card - either outcome is fine
    }
  })

  test('Anvi adds a fresh topic to DIP, generates its bank, and approves all', async ({ page }) => {
    // Real provider latency: claude_sonnet fails fast (no key configured this session), then
    // gemini_flash generates a full 12-15 item structured bank - observed to sometimes need its
    // one same-provider parse retry too, so budget for two real generation calls, not one.
    test.setTimeout(240_000)

    await login(page, ANVI.identifier, ANVI.password)
    await expect(page).toHaveURL(/\/teacher/)

    await page.getByRole('button', { name: 'Digital Image Processing (DIP)' }).click()

    // Fresh topic, added straight into the already-published "Frequency Domain" chapter (M3 model:
    // chapters are the only publish lever - a block added to an already-published chapter is
    // immediately visible, no separate re-publish step).
    await page.getByLabel('New topic title').fill(TOPIC_TITLE)
    await page.getByRole('button', { name: 'Add topic', exact: true }).click()
    await expect(page.getByRole('listitem').filter({ hasText: TOPIC_TITLE }).first()).toBeVisible()

    await page.getByLabel('Pick a topic for Frequency Domain').selectOption({ label: TOPIC_TITLE })
    await page.getByRole('button', { name: 'Add topic block to Frequency Domain' }).click()
    await expect(page.getByText(`Assessment: Unit Check 1`)).toBeVisible() // sanity: builder still rendering the chapter

    // Two listitems now contain this title (the Topics list AND the chapter's block list) - scope
    // to the one that actually has the "Review bank" button, not DOM order.
    const topicRow = page.getByRole('listitem').filter({ has: page.getByRole('button', { name: 'Review bank' }) }).filter({ hasText: TOPIC_TITLE })
    await topicRow.getByRole('button', { name: 'Review bank' }).click()
    await expect(page.getByRole('heading', { name: new RegExp(`Item bank: ${TOPIC_TITLE}`) })).toBeVisible()

    await page.getByRole('button', { name: 'Generate bank' }).click()
    // Real LLM call - wait for the draft items to render.
    await expect(page.getByRole('button', { name: /^Approve:/ }).first()).toBeVisible({ timeout: 200_000 })
    // config/ai.yaml's item_bank.min_items/max_items is a range (12-15), not a fixed count.
    const approveCount = await page.getByRole('button', { name: /^Approve:/ }).count()
    expect(approveCount).toBeGreaterThanOrEqual(12)
    expect(approveCount).toBeLessThanOrEqual(15)

    await page.getByRole('button', { name: 'Approve all' }).click()
    await expect(page.getByRole('button', { name: /^Approve:/ })).toHaveCount(0)
  })

  test('Yash takes the 5-question probe and the review screen shows stored reasoning + mastery', async ({ page }) => {
    await login(page, YASH.identifier, YASH.password)
    await expect(page).toHaveURL(/\/student/)

    await page.getByRole('button', { name: 'Digital Image Processing (DIP)' }).click()
    await page.getByRole('button', { name: TOPIC_TITLE }).click()

    await expect(page.getByText('Question 1 of 5')).toBeVisible()
    for (let i = 1; i <= 5; i++) {
      await expect(page.getByText(`Question ${i} of 5`)).toBeVisible()
      const options = page.getByRole('listitem').getByRole('button')
      await options.first().click()
    }

    // End-of-probe review (S3: deferred feedback) - stored reasoning + mastery both visible.
    await expect(page.getByText(/\d \/ 5 correct/)).toBeVisible()
    await expect(page.getByRole('heading', { name: /^Q1\./ })).toBeVisible()
    await expect(page.getByRole('heading', { name: /^Q5\./ })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Mastery' })).toBeVisible()
    await expect(page.getByText(new RegExp(`${TOPIC_TITLE}: \\d+%`))).toBeVisible()
  })
})

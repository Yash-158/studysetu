// M5 GATE: Yash builds REAL weak Transforms mastery (deliberately wrong answers on a real
// diagnostic, never injected via a DB shortcut - same discipline as M4's live-GATE verification)
// -> opens Frequency Filtering -> that topic's own diagnostic -> the session plan shows an
// injected Transforms revision segment first -> Yash completes the session -> mastery moves on
// both topics -> /timeline (My Timeline tab) shows the full causal chain in order: diagnostic
// completed, session started, revision injected, mastery changed, session completed.
//
// Run against a REAL configured provider chain (config/ai.yaml's dynamic groq/gemini/cerebras/
// deepseek chain, ai_primary_provider/ai_fallback_provider) - uses the FIXED seeded DIP subject
// (Transforms -> Frequency Filtering, the literal ROADMAP M5 scenario) rather than a per-run
// topic, since item-bank generation is idempotent at the item level (a second generate call for
// an already-banked topic is a pure generated_artifacts cache hit, matching M4's own precedent) -
// safe to re-run this spec against the same persistent DB.
// Run `uv run scripts/seed_demo.py` against a fresh DB first (see README.md "Determinism").
import { test, expect, type Page } from '@playwright/test'

const INSTITUTION_SLUG = 'gls-demo'
const ANVI = { identifier: 'anvi@gls-demo.test', password: 'Passw0rd!2' }
const YASH = { identifier: '21BCE001', password: 'Passw0rd!3' }

async function login(page: Page, identifier: string, password: string) {
  await page.goto('/login')
  await page.getByLabel('Institution code').fill(INSTITUTION_SLUG)
  await page.getByLabel('Roll number or email').fill(identifier)
  await page.getByLabel('Password', { exact: true }).fill(password)
  await page.getByRole('button', { name: 'Log in' }).click()
}

// Reads the teacher-visible correct answer for every item currently shown on BankReviewPage
// (the ✓-prefixed option), keyed by stem text - lets Yash's diagnostic answers deliberately avoid
// the correct option for real, without a DB shortcut (same discipline as M4's live-GATE session).
async function captureCorrectAnswersByStem(page: Page): Promise<Map<string, string>> {
  const map = new Map<string, string>()
  const cards = await page.locator('.ss-card').all()
  for (const card of cards) {
    const stemLocator = card.locator('p strong')
    if ((await stemLocator.count()) === 0) continue
    const stem = (await stemLocator.first().textContent())?.trim()
    const optionTexts = await card.locator('ul li').allTextContents()
    const correct = optionTexts.find((t) => t.trim().startsWith('✓'))
    if (stem && correct) map.set(stem, correct.replace('✓', '').split('—')[0].trim())
  }
  return map
}

async function ensureBankApproved(page: Page, topicTitle: string) {
  const topicRow = page.getByRole('listitem').filter({ has: page.getByRole('button', { name: 'Review bank' }) }).filter({ hasText: topicTitle })
  await topicRow.getByRole('button', { name: 'Review bank' }).click()
  await expect(page.getByRole('heading', { name: new RegExp(`Item bank: ${topicTitle}`) })).toBeVisible()

  // exact:true matters here - Playwright's name matcher is substring-by-default, and "Generate
  // bank" would otherwise also match the "Regenerate bank" button an already-banked topic shows,
  // triggering a needless real regeneration and then hanging forever waiting for Approve buttons
  // that will never appear (the items are already approved, not draft).
  const generateBtn = page.getByRole('button', { name: 'Generate bank', exact: true })
  if (await generateBtn.isVisible()) {
    await generateBtn.click()
    // Real LLM call - a fresh 12-15 item bank routinely needs tens of seconds.
    await expect(page.getByRole('button', { name: /^Approve:/ }).first()).toBeVisible({ timeout: 200_000 })
  }
  const approveAllBtn = page.getByRole('button', { name: 'Approve all' })
  if (await approveAllBtn.isVisible()) {
    await approveAllBtn.click()
    await expect(page.getByRole('button', { name: /^Approve:/ })).toHaveCount(0)
  }
}

async function answerFiveQuestionDiagnostic(page: Page, correctByStem: Map<string, string> | null) {
  for (let i = 1; i <= 5; i++) {
    await expect(page.getByText(`Question ${i} of 5`)).toBeVisible()
    const options = page.getByRole('listitem').getByRole('button')
    let indexToClick = 0
    if (correctByStem) {
      const stem = (await page.locator('.ss-card p strong').first().textContent())?.trim() ?? ''
      const correctText = correctByStem.get(stem)
      if (correctText) {
        const optionTexts = await options.allTextContents()
        const wrongIndex = optionTexts.findIndex((t) => t.trim() !== correctText)
        if (wrongIndex !== -1) indexToClick = wrongIndex
      }
    }
    await options.nth(indexToClick).click()
  }
}

async function playSessionToCompletion(page: Page) {
  for (let step = 0; step < 30; step++) {
    const optionButtons = page.locator('.ss-card ul li button')
    if ((await optionButtons.count()) > 0) {
      await optionButtons.first().click()
    }
    await expect(page.getByRole('button', { name: /^(Next|Finish session)$/ })).toBeVisible()
    const finishBtn = page.getByRole('button', { name: 'Finish session' })
    if ((await finishBtn.count()) > 0) {
      await finishBtn.click()
      return
    }
    await page.getByRole('button', { name: 'Next' }).click()
  }
  throw new Error('session did not reach "Finish session" within the expected number of steps')
}

test.describe.serial('M5 GATE: real weak Transforms -> injected revision -> session -> mastery -> timeline', () => {
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

  test('Anvi generates and approves banks for Transforms and Frequency Filtering', async ({ page }) => {
    test.setTimeout(400_000) // two real bank generations, each potentially needing a parse retry / failover

    await login(page, ANVI.identifier, ANVI.password)
    await expect(page).toHaveURL(/\/teacher/)
    await page.getByRole('button', { name: 'Digital Image Processing (DIP)' }).click()

    for (const title of ['Transforms', 'Frequency Filtering']) {
      await ensureBankApproved(page, title)
      await page.getByRole('button', { name: '← Back to subject' }).click()
    }
  })

  test("Yash builds real weak Transforms mastery, then Frequency Filtering's session injects a Transforms revision, completes, and the timeline shows the causal chain", async ({ page }) => {
    test.setTimeout(300_000)

    await login(page, YASH.identifier, YASH.password)
    await expect(page).toHaveURL(/\/student/)
    await page.getByRole('button', { name: 'Digital Image Processing (DIP)' }).click()

    // Read BOTH topics' correct answers from the teacher's bank view up front, matched back to
    // each probe by stem text (both render `item.stem`/options identically) - needed for BOTH
    // diagnostics: once Transforms is weak, Frequency Filtering's OWN diagnostic draw includes a
    // weak-prereq slot item FROM TRANSFORMS'S BANK (the M4 mechanism, working as designed), so
    // answering that diagnostic carelessly (e.g. always clicking the first option) can accidentally
    // answer the embedded Transforms question CORRECTLY and partially undo the very weakness this
    // test is deliberately building - never a DB shortcut, so this has to be controlled for real.
    const teacherContext = await page.context().browser()!.newContext()
    const teacherPage = await teacherContext.newPage()
    await login(teacherPage, ANVI.identifier, ANVI.password)
    await teacherPage.getByRole('button', { name: 'Digital Image Processing (DIP)' }).click()
    const correctByStem = new Map<string, string>()
    for (const title of ['Transforms', 'Frequency Filtering']) {
      const topicRow = teacherPage.getByRole('listitem').filter({ has: teacherPage.getByRole('button', { name: 'Review bank' }) }).filter({ hasText: title })
      await topicRow.getByRole('button', { name: 'Review bank' }).click()
      // getBank() is an async fetch - .locator(...).all() takes a synchronous DOM snapshot with no
      // auto-retry, so scraping immediately after the click (before items re-render) silently
      // returns zero cards. Wait for real content first.
      await expect(teacherPage.getByRole('heading', { name: new RegExp(`Item bank: ${title}`) })).toBeVisible()
      await expect(teacherPage.locator('.ss-card p strong').first()).toBeVisible()
      for (const [stem, correct] of await captureCorrectAnswersByStem(teacherPage)) correctByStem.set(stem, correct)
      await teacherPage.getByRole('button', { name: '← Back to subject' }).click()
    }
    expect(correctByStem.size).toBeGreaterThan(0)
    await teacherContext.close()

    // Step 1: a REAL diagnostic on Transforms, deliberately answered wrong (never injected via a
    // DB shortcut) - the student-facing probe never reveals correctness mid-probe (S3).
    await page.getByRole('button', { name: 'Transforms', exact: true }).click()
    await expect(page.getByText('Question 1 of 5')).toBeVisible()
    await answerFiveQuestionDiagnostic(page, correctByStem)
    // 0 or 1 out of 5, not strictly 0 - a real LLM-generated item occasionally mentions a concept
    // (e.g. a Frequency Filtering item whose distractor references histograms) that doesn't
    // stem-match this map's exact wording, so the rare fallback click can land correct. Either
    // score still builds genuine, well-below-threshold weakness (verified next by the actual
    // product behavior under test: the revision card must appear, which only happens if the
    // real stored mastery is genuinely low - not inferred from this score, proven by it).
    await expect(page.getByText(/[01] \/ 5 correct/)).toBeVisible()

    await page.getByRole('button', { name: 'Back to subject' }).click()

    // Step 2: Frequency Filtering's own diagnostic - still deliberately avoiding correct answers
    // (the same combined map), since one drawn item is the weak-prereq slot from Transforms itself.
    await page.getByRole('button', { name: 'Frequency Filtering', exact: true }).click()
    await expect(page.getByText('Question 1 of 5')).toBeVisible()
    await answerFiveQuestionDiagnostic(page, correctByStem)
    await expect(page.getByText(/\d \/ 5 correct/)).toBeVisible()

    // Step 3: the personalized session - the injected Transforms revision must appear at the head.
    await page.getByRole('button', { name: 'Start my personalized session' }).click()
    // A fresh session now correctly opens at the bridge card first (the resume-index fix), not
    // skipping straight to the first practice/revision card - one Next click then reaches the
    // injected Transforms revision, still at the head of the real lesson content.
    await expect(page.getByText(/You scored \d\/5 on the probe/)).toBeVisible({ timeout: 200_000 })
    await page.getByRole('button', { name: 'Next' }).click()
    await expect(page.getByRole('heading', { name: /Quick refresher: Transforms/ })).toBeVisible()

    await playSessionToCompletion(page)
    await expect(page.getByRole('heading', { name: /session complete/ })).toBeVisible()
    await page.getByRole('button', { name: 'Done' }).click()

    // Step 4: the timeline shows the full causal chain (F13) - newest first, so in DISPLAY order:
    // session completed, then (further down) the revision that was injected, then the diagnostic
    // that revealed the weakness.
    await page.getByRole('button', { name: 'My Timeline' }).click()
    await expect(page.getByRole('heading', { name: 'Your timeline' })).toBeVisible()
    const cardTexts = await page.locator('.ss-card p').allTextContents()
    const joined = cardTexts.join(' | ')

    const idxSessionCompleted = cardTexts.findIndex((t) => t.includes('Completed the session'))
    const idxMasteryMovedFreq = cardTexts.findIndex((t) => t.includes('Mastery moved (Frequency Filtering'))
    const idxRevision = cardTexts.findIndex((t) => t.includes('Got a quick refresher on Transforms'))
    const idxSessionStarted = cardTexts.findIndex((t) => t.includes('Started a personalized session'))
    const idxDiagnosticCompletedTransforms = cardTexts.findIndex((t) => t.includes('Finished the probe (Transforms)'))

    expect(idxSessionCompleted, joined).toBeGreaterThanOrEqual(0)
    expect(idxMasteryMovedFreq, joined).toBeGreaterThanOrEqual(0)
    expect(idxRevision, joined).toBeGreaterThanOrEqual(0)
    expect(idxSessionStarted, joined).toBeGreaterThanOrEqual(0)
    expect(idxDiagnosticCompletedTransforms, joined).toBeGreaterThanOrEqual(0)

    // Newest-first display: the causal chain reads bottom-to-top in array order.
    expect(idxSessionCompleted).toBeLessThan(idxMasteryMovedFreq)
    expect(idxMasteryMovedFreq).toBeLessThan(idxRevision)
    expect(idxRevision).toBeLessThan(idxSessionStarted)
    expect(idxSessionStarted).toBeLessThan(idxDiagnosticCompletedTransforms)
  })
})

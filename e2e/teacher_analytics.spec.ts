// M6 GATE: a real cluster on Today -> drill cluster -> student -> the exact wrong attempts ->
// flag one AI artifact; plus the enrollment-archive Verify line and designed empty states.
//
// Determinism trick (no DB shortcut on the thing under test - same discipline as every prior
// milestone's GATE): a fresh topic with ZERO prerequisite edges is built so the stratified
// diagnostic draw (1 easy / 2 medium / 1 hard + a 5th weak-prereq-or-fallback slot, see
// modules/learning.py) has nowhere random to hide once exactly 1 easy + 3 medium + 1 hard items
// are approved (5 total, matching probe_size exactly) - the medium bucket takes a random 2 of the
// 3 approved mediums, but the 3rd always fills the 5th "fallback" slot (fallback prefers
// difficulty=medium when any remains), so EVERY student's draw is guaranteed to be the exact same
// 5 approved items regardless of shuffle order. 5 distinct real students then each independently
// pick the SAME real wrong option (captured from the teacher's own bank-review view, never
// hardcoded) on the shared item, producing a genuine 5-count misconception cluster - whatever
// title the live LLM actually gave that misconception, not an invented string.
//
// Run `uv run scripts/seed_demo.py` against a fresh DB first (see README.md "Determinism"). Uses
// a per-run unique subject/topic name suffix so the spec is re-runnable against the same
// persistent DB, and reuses the seeded CSE-3A pool students (21BCE002-21BCE006).
import { test, expect, type Page } from '@playwright/test'

const INSTITUTION_SLUG = 'gls-demo'
const ANVI = { identifier: 'anvi@gls-demo.test', password: 'Passw0rd!2' }
const RUN_ID = Date.now().toString().slice(-6)
const SUBJECT_NAME = `M6 Analytics ${RUN_ID}`
const CHAPTER_TITLE = 'Ch1'
const TOPIC_TITLE = `Distribution Law ${RUN_ID}`

// 5 of the seeded CSE-3A pool students (scripts/seed_demo.py: 21BCE00{n}, activation code
// 4000000{n-1}) - never activated by any other spec so far, so each gets its own fresh password.
const STUDENTS = [2, 3, 4, 5, 6].map((n) => ({
  roll: `21BCE00${n}`,
  code: `4000000${n - 1}`,
  password: `Passw0rd!S${n}`,
}))

type BankItem = { stem: string; difficulty: 'Easy' | 'Medium' | 'Hard'; options: { body: string; isCorrect: boolean; misconceptionTitle: string | null }[] }

async function login(page: Page, identifier: string, password: string) {
  await page.goto('/login')
  await page.getByLabel('Institution code').fill(INSTITUTION_SLUG)
  await page.getByLabel('Roll number or email').fill(identifier)
  await page.getByLabel('Password', { exact: true }).fill(password)
  await page.getByRole('button', { name: 'Log in' }).click()
}

// Reads every currently-shown bank item's stem, difficulty, and (for wrong options) misconception
// title - same DOM-scraping discipline as learning_session.spec.ts's captureCorrectAnswersByStem,
// extended to also read the difficulty pill and misconception text BankReviewPage renders.
async function captureBank(page: Page): Promise<BankItem[]> {
  const items: BankItem[] = []
  for (const card of await page.locator('.ss-card').all()) {
    const stemLocator = card.locator('p strong')
    if ((await stemLocator.count()) === 0) continue
    const stem = (await stemLocator.first().textContent())?.trim() ?? ''
    const pillTexts = await card.locator('p').first().locator('.ss-status-pill').allTextContents()
    const difficulty = pillTexts.map((t) => t.trim()).find((t) => t === 'Easy' || t === 'Medium' || t === 'Hard') as BankItem['difficulty'] | undefined
    if (!difficulty) continue
    const optionTexts = await card.locator('ul li').allTextContents()
    const options = optionTexts.map((raw) => {
      const isCorrect = raw.trim().startsWith('✓')
      const withoutTick = raw.replace('✓', '').trim()
      const [body, misconceptionPart] = withoutTick.split('—').map((s) => s.trim())
      const misconceptionTitle = misconceptionPart ? misconceptionPart.replace(/^misconception:\s*/, '') : null
      return { body, isCorrect, misconceptionTitle }
    })
    items.push({ stem, difficulty, options })
  }
  return items
}

async function answerFiveQuestionDiagnostic(page: Page, targetStem: string, targetWrongBody: string) {
  for (let i = 1; i <= 5; i++) {
    await expect(page.getByText(`Question ${i} of 5`)).toBeVisible()
    const stem = (await page.locator('.ss-card p strong').first().textContent())?.trim() ?? ''
    const options = page.getByRole('listitem').getByRole('button')
    if (stem === targetStem) {
      await options.filter({ hasText: targetWrongBody }).first().click()
    } else {
      await options.first().click()
    }
  }
  await expect(page.getByText(/\d \/ 5 correct/)).toBeVisible()
}

// Shared across this file's serial tests (same worker, run in order - same pattern every prior
// milestone's e2e suite uses for cross-test state within one describe.serial block).
let target: { stem: string; wrongBody: string; misconceptionTitle: string } | null = null

test.describe.serial('M6 GATE: real misconception cluster -> student drill-down -> flag -> enrollment-archive respected', () => {
  test('empty states: a brand-new self-serve teacher with zero activity sees the designed empty copy on Today', async ({ page }) => {
    const soloId = Date.now().toString().slice(-6)
    await page.goto('/teacher-signup')
    await page.getByLabel('Classroom / institution name').fill(`M6 Empty ${soloId}`)
    await page.getByLabel('Your name').fill('Solo Teacher')
    await page.getByLabel('Email').fill(`m6-empty-${soloId}@e2e.local`)
    await page.getByLabel('Password').fill('SoloPass!1')
    await page.getByRole('button', { name: 'Create my classroom' }).click()
    await expect(page).toHaveURL(/\/teacher/)

    await page.getByRole('button', { name: 'Analytics', exact: true }).click()
    await expect(page.getByText('No cluster has crossed the alert threshold yet')).toBeVisible()
    await expect(page.getByText('Nobody is currently stalled')).toBeVisible()
    await expect(page.getByText('No item banks are awaiting review.')).toBeVisible()
  })

  test('Anvi activates (seeded account, first run only)', async ({ page }) => {
    await page.goto('/activate')
    await page.getByLabel('Institution code').fill(INSTITUTION_SLUG)
    await page.getByLabel('Roll number or email').fill(ANVI.identifier)
    await page.getByLabel('Activation code').fill('22222222')
    await page.getByLabel('New password').fill(ANVI.password)
    await page.getByLabel('Confirm password').fill(ANVI.password)
    await page.getByRole('button', { name: 'Activate' }).click()
    await page.waitForTimeout(300) // already-active on a rerun shows an error card - either outcome is fine
  })

  test('Anvi builds a fresh no-prereq topic, generates a real bank, and approves exactly 1 easy/3 medium/1 hard items', async ({ page }) => {
    test.setTimeout(400_000) // real LLM generation

    await login(page, ANVI.identifier, ANVI.password)
    await expect(page).toHaveURL(/\/teacher/)

    // Create the subject (SubjectsPage's create form auto-selects it into the builder).
    await page.getByLabel('Name').fill(SUBJECT_NAME)
    await page.getByRole('button', { name: 'Create subject' }).click()
    await expect(page.getByRole('heading', { name: new RegExp(SUBJECT_NAME) })).toBeVisible()

    await page.getByLabel('New chapter title').fill(CHAPTER_TITLE)
    await page.getByRole('button', { name: 'Add chapter' }).click()
    await expect(page.getByText(CHAPTER_TITLE, { exact: true })).toBeVisible()

    await page.getByLabel('New topic title').fill(TOPIC_TITLE)
    await page.getByRole('button', { name: 'Add topic', exact: true }).click()
    const topicListRow = page.getByRole('listitem').filter({ has: page.getByRole('button', { name: 'Review bank' }) }).filter({ hasText: TOPIC_TITLE })
    await expect(topicListRow).toBeVisible()

    await page.getByLabel(`Pick a topic for ${CHAPTER_TITLE}`).selectOption({ label: TOPIC_TITLE })
    await page.getByLabel(`Add topic block to ${CHAPTER_TITLE}`).click()
    // Two <li> can now contain this text (the chapter's block list AND the Topics card's own
    // list) - .first() just confirms the block landed, the later Review-bank-scoped locator is
    // what actually disambiguates for the click.
    await expect(page.getByRole('listitem').filter({ hasText: TOPIC_TITLE }).first()).toBeVisible()

    await page.getByRole('button', { name: `Publish ${CHAPTER_TITLE}` }).click()
    await expect(page.getByRole('button', { name: `Publish ${CHAPTER_TITLE}` })).toHaveCount(0)

    // M6-remediation: the builder is now staged (Structure/Prerequisites/Materials/Roster) - Pools
    // and Enrollments both live under Roster.
    await page.getByRole('button', { name: 'Roster', exact: true }).click()
    await page.getByLabel('Pick a pool').selectOption({ label: 'CSE-3A' })
    await page.getByRole('button', { name: 'Attach pool' }).click()
    // Confirms the attach really landed (Enrollments card is now populated) - also the exact
    // control this spec uses later to archive one contributor.
    await expect(page.getByRole('button', { name: 'Remove Student 2', exact: true })).toBeVisible()

    // Generate + inspect the real bank ("Review bank" lives in the Topics card, back under Structure).
    await page.getByRole('button', { name: 'Structure', exact: true }).click()
    await topicListRow.getByRole('button', { name: 'Review bank' }).click()
    await expect(page.getByRole('heading', { name: new RegExp(`Item bank: ${TOPIC_TITLE}`) })).toBeVisible()
    await page.getByRole('button', { name: 'Generate bank', exact: true }).click()
    await expect(page.getByRole('button', { name: /^Approve:/ }).first()).toBeVisible({ timeout: 200_000 })

    const bank = await captureBank(page)
    const byDifficulty = {
      Easy: bank.filter((i) => i.difficulty === 'Easy'),
      Medium: bank.filter((i) => i.difficulty === 'Medium'),
      Hard: bank.filter((i) => i.difficulty === 'Hard'),
    }
    expect(byDifficulty.Easy.length, `bank: ${JSON.stringify(bank.map((i) => i.difficulty))}`).toBeGreaterThanOrEqual(1)
    expect(byDifficulty.Medium.length).toBeGreaterThanOrEqual(3)
    expect(byDifficulty.Hard.length).toBeGreaterThanOrEqual(1)

    // Every draw for this topic will be exactly these 5 items, regardless of shuffle (see header
    // comment) - the target misconception comes from the easy item's first real wrong option.
    const toApprove = [byDifficulty.Easy[0], ...byDifficulty.Medium.slice(0, 3), byDifficulty.Hard[0]]
    const targetItem = byDifficulty.Easy[0]
    const targetWrong = targetItem.options.find((o) => !o.isCorrect && o.misconceptionTitle)
    expect(targetWrong, JSON.stringify(targetItem)).toBeTruthy()
    target = { stem: targetItem.stem, wrongBody: targetWrong!.body, misconceptionTitle: targetWrong!.misconceptionTitle! }

    for (const item of toApprove) {
      await page.getByRole('button', { name: `Approve: ${item.stem}` }).click()
    }
    await expect(page.getByRole('button', { name: `Approve: ${target.stem}` })).toHaveCount(0)

    // The remaining generated-but-unapproved items are the "ungraded" signal's job to surface.
    expect(bank.length).toBeGreaterThan(toApprove.length)
  })

  for (const student of STUDENTS) {
    test(`${student.roll} activates and answers the diagnostic, picking the shared target wrong option`, async ({ page }) => {
      test.setTimeout(60_000)
      await page.goto('/activate')
      await page.getByLabel('Institution code').fill(INSTITUTION_SLUG)
      await page.getByLabel('Roll number or email').fill(student.roll)
      await page.getByLabel('Activation code').fill(student.code)
      await page.getByLabel('New password').fill(student.password)
      await page.getByLabel('Confirm password').fill(student.password)
      await page.getByRole('button', { name: 'Activate' }).click()
      await page.waitForTimeout(300) // already-active on a rerun shows an error card - either outcome is fine

      await login(page, student.roll, student.password)
      await expect(page).toHaveURL(/\/student/)
      await page.getByRole('button', { name: SUBJECT_NAME }).click()
      await page.getByRole('button', { name: TOPIC_TITLE, exact: true }).click()
      expect(target, 'target misconception must be captured by the previous serial test').toBeTruthy()
      await answerFiveQuestionDiagnostic(page, target!.stem, target!.wrongBody)
    })
  }

  test("Anvi's Today view shows the real 5-count cluster, drills to a student, sees the exact wrong attempt, and flags the bank artifact", async ({ page }) => {
    expect(target).toBeTruthy()
    await login(page, ANVI.identifier, ANVI.password)
    await expect(page).toHaveURL(/\/teacher/)
    await page.getByRole('button', { name: 'Analytics', exact: true }).click()

    // TodayPage renders the cluster's summary line and its student buttons as two sibling <p>s
    // inside one wrapper div - scope to that wrapper, not just the summary <p>, so the student
    // buttons are reachable from the same locator.
    const clusterCard = page.locator('.ss-stack-tight').filter({ hasText: TOPIC_TITLE }).filter({ hasText: target!.misconceptionTitle })
    await expect(clusterCard).toBeVisible()
    await expect(clusterCard).toContainText('5 students')

    // The "ungraded" signal surfaces the same topic's leftover draft items.
    const ungradedRow = page.locator('p').filter({ hasText: TOPIC_TITLE }).filter({ hasText: 'awaiting review' })
    await expect(ungradedRow).toBeVisible()

    // Drill: cluster -> one of its students (any of the 5 contributors has the identical wrong attempt).
    await clusterCard.locator('button').first().click()
    await expect(page.getByRole('heading', { level: 2 })).toBeVisible()
    await expect(page.getByText(target!.stem)).toBeVisible()
    await expect(page.getByText(`Chose: ${target!.wrongBody}`)).toBeVisible()
    await expect(page.getByText(`misconception: ${target!.misconceptionTitle}`)).toBeVisible()

    // Flag the one AI artifact (the topic's item bank) - F14.
    const flagButton = page.getByRole('button', { name: 'Flag' }).first()
    await flagButton.click()
    await expect(page.getByText('Flagged for review.')).toBeVisible()
    await expect(page.getByText('flagged', { exact: true })).toBeVisible()

    // Archive ONE KNOWN contributor's enrollment (STUDENTS[0] = 21BCE002 = display name "Student
    // 2", a real cluster contributor - archiving an uninvolved CSE-3A pool member wouldn't move
    // this count at all) - Verify line: analytics respect enrollment archive status. Back to the
    // subject builder's Enrollments card, the real removal action.
    await page.getByRole('button', { name: 'Subjects' }).click()
    await page.getByRole('button', { name: new RegExp(SUBJECT_NAME) }).click()
    await page.getByRole('button', { name: 'Roster', exact: true }).click()
    await page.getByRole('button', { name: 'Remove Student 2', exact: true }).click()

    await page.getByRole('button', { name: 'Analytics', exact: true }).click()
    await expect(page.locator('p').filter({ hasText: TOPIC_TITLE }).filter({ hasText: target!.misconceptionTitle })).toHaveCount(0)
  })
})

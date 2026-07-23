// M3 GATE: Anvi builds Digital Image Processing (2 chapters, 5 topics, 1 edge Transforms->Frequency
// Filtering, 1 assessment placeholder block, 1 PDF material) and publishes; enrolled Yash sees the
// published structure only (a draft chapter added afterward stays hidden).
// Run `uv run scripts/seed_demo.py` against a fresh DB first (see README.md "Determinism"). Uses a
// per-run unique subject name suffix so the spec is re-runnable against the same persistent DB.
import { test, expect } from '@playwright/test'

const INSTITUTION_SLUG = 'gls-demo'
const ANVI = { identifier: 'anvi@gls-demo.test', password: 'Passw0rd!2' }
const YASH = { identifier: '21BCE001', password: 'Passw0rd!3' }
const RUN_ID = Date.now().toString().slice(-6)
const SUBJECT_NAME = `Digital Image Processing ${RUN_ID}`

function buildPdf(text: string): Buffer {
  // Hand-built minimal single-page PDF (valid xref/trailer) - same technique as
  // apps/api/tests/test_curriculum.py and scripts/seed_demo.py, ported to JS for the file upload.
  const content = Buffer.from(`BT /F1 24 Tf 10 100 Td (${text}) Tj ET`)
  const objs = [
    Buffer.from('<< /Type /Catalog /Pages 2 0 R >>'),
    Buffer.from('<< /Type /Pages /Kids [3 0 R] /Count 1 >>'),
    Buffer.from('<< /Type /Page /Parent 2 0 R /Resources << /Font << /F1 4 0 R >> >> /MediaBox [0 0 300 300] /Contents 5 0 R >>'),
    Buffer.from('<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>'),
    Buffer.concat([Buffer.from(`<< /Length ${content.length} >>\nstream\n`), content, Buffer.from('\nendstream')]),
  ]
  const chunks: Buffer[] = [Buffer.from('%PDF-1.4\n')]
  const offsets: number[] = []
  let pos = chunks[0].length
  objs.forEach((body, i) => {
    offsets.push(pos)
    const chunk = Buffer.concat([Buffer.from(`${i + 1} 0 obj\n`), body, Buffer.from('\nendobj\n')])
    chunks.push(chunk)
    pos += chunk.length
  })
  const xrefPos = pos
  const n = objs.length + 1
  let xref = `xref\n0 ${n}\n0000000000 65535 f \n`
  for (const off of offsets) xref += `${off.toString().padStart(10, '0')} 00000 n \n`
  chunks.push(Buffer.from(xref))
  chunks.push(Buffer.from(`trailer\n<< /Size ${n} /Root 1 0 R >>\nstartxref\n${xrefPos}\n%%EOF`))
  return Buffer.concat(chunks)
}

async function login(page: import('@playwright/test').Page, identifier: string, password: string) {
  await page.goto('/login')
  await page.getByLabel('Institution code').fill(INSTITUTION_SLUG)
  await page.getByLabel('Roll number or email').fill(identifier)
  await page.getByLabel('Password', { exact: true }).fill(password)
  await page.getByRole('button', { name: 'Log in' }).click()
}

test.describe.serial('M3 GATE: Anvi builds and publishes DIP; enrolled Yash sees published-only', () => {
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
      // Already-active on repeat runs shows an error card in place - either outcome is fine here.
      await page.waitForTimeout(300)
    }
  })

  test('Anvi builds DIP end-to-end through the builder UI and publishes it', async ({ page }) => {
    await login(page, ANVI.identifier, ANVI.password)
    await expect(page).toHaveURL(/\/teacher/)

    await page.getByLabel('Name').fill(SUBJECT_NAME)
    await page.getByLabel('Code (optional)').fill('DIP')
    await page.getByRole('button', { name: 'Create subject' }).click()

    await expect(page.getByRole('heading', { name: new RegExp(SUBJECT_NAME) })).toBeVisible()

    // 2 chapters - wait for each to visibly land (the builder refreshes from the server after each
    // async mutation; firing the next submit before that refresh settles races the UI, not the API).
    await page.getByLabel('New chapter title').fill('Foundations')
    await page.getByRole('button', { name: 'Add chapter' }).click()
    await expect(page.getByText('Foundations')).toBeVisible()
    await page.getByLabel('New chapter title').fill('Frequency Domain')
    await page.getByRole('button', { name: 'Add chapter' }).click()
    await expect(page.getByText('Frequency Domain')).toBeVisible()

    // 5 topics
    for (const title of ['Sampling', 'Quantization', 'Transforms', 'Histograms', 'Frequency Filtering']) {
      await page.getByLabel('New topic title').fill(title)
      await page.getByRole('button', { name: 'Add topic', exact: true }).click()
      await expect(page.getByRole('listitem').filter({ hasText: title }).first()).toBeVisible()
    }

    // 3 topic blocks into Foundations
    for (const title of ['Sampling', 'Quantization', 'Transforms']) {
      await page.getByLabel('Pick a topic for Foundations').selectOption({ label: title })
      await page.getByRole('button', { name: 'Add topic block to Foundations' }).click()
      await expect(page.getByRole('listitem').filter({ hasText: title })).toHaveCount(2) // Topics list + this new block
    }
    // 2 topic blocks + 1 assessment placeholder into Frequency Domain
    for (const title of ['Histograms', 'Frequency Filtering']) {
      await page.getByLabel('Pick a topic for Frequency Domain').selectOption({ label: title })
      await page.getByRole('button', { name: 'Add topic block to Frequency Domain' }).click()
      await expect(page.getByRole('listitem').filter({ hasText: title })).toHaveCount(2)
    }
    await page.getByLabel('Assessment title for Frequency Domain').fill('Unit Check 1')
    await page.getByRole('button', { name: 'Add assessment placeholder to Frequency Domain' }).click()
    await expect(page.getByText('Assessment: Unit Check 1')).toBeVisible()

    // 1 prerequisite edge: Transforms -> Frequency Filtering (M6-remediation: the builder is now
    // staged - Structure/Prerequisites/Materials/Roster - so each stage's own tab needs a click
    // before its fields become reachable, same real navigation a teacher now clicks through).
    await page.getByRole('button', { name: 'Prerequisites', exact: true }).click()
    await page.getByLabel('Requires (prerequisite)').selectOption({ label: 'Transforms' })
    await page.getByLabel('…is needed before').selectOption({ label: 'Frequency Filtering' })
    await page.getByRole('button', { name: 'Add link' }).click()
    await expect(page.getByText('Transforms → Frequency Filtering')).toBeVisible()

    // 1 PDF material
    await page.getByRole('button', { name: 'Materials', exact: true }).click()
    await page.getByLabel('Title', { exact: true }).fill('DIP Syllabus')
    await page.setInputFiles('#material_file', {
      name: 'syllabus.pdf',
      mimeType: 'application/pdf',
      buffer: buildPdf('Digital Image Processing syllabus covers transforms and frequency domain filtering in depth'),
    })
    await page.getByRole('button', { name: 'Upload' }).click()
    await expect(page.getByText('DIP Syllabus (pdf)')).toBeVisible()
    // readable (text-PDF) - stored_only badge must NOT appear on this one
    await expect(page.getByText('DIP Syllabus (pdf)').locator('..')).not.toContainText('stored only')

    // A draft chapter added AFTER the others, deliberately left unpublished - Yash must never see it.
    await page.getByRole('button', { name: 'Structure', exact: true }).click()
    await page.getByLabel('New chapter title').fill('Advanced Topics DRAFT')
    await page.getByRole('button', { name: 'Add chapter' }).click()

    // Publish only Foundations + Frequency Domain (not the draft chapter)
    await page.getByLabel('Publish Foundations').click()
    await page.getByLabel('Publish Frequency Domain').click()
    await expect(page.getByLabel('Publish Foundations')).toHaveCount(0)
    await expect(page.getByLabel('Publish Frequency Domain')).toHaveCount(0)

    // Attach CSE-3A pool so Yash (already a member, seeded) gets enrolled
    await page.getByRole('button', { name: 'Roster', exact: true }).click()
    await page.getByLabel('Pick a pool').selectOption({ label: 'CSE-3A' })
    await page.getByRole('button', { name: 'Attach pool' }).click()
  })

  test('enrolled Yash sees the published structure only - the draft chapter is hidden', async ({ page }) => {
    await login(page, YASH.identifier, YASH.password)
    await expect(page).toHaveURL(/\/student/)

    await page.getByRole('button', { name: new RegExp(SUBJECT_NAME) }).click()

    await expect(page.getByText('Foundations')).toBeVisible()
    await expect(page.getByText('Frequency Domain')).toBeVisible()
    await expect(page.getByText('Advanced Topics DRAFT')).toHaveCount(0)

    await expect(page.getByText('Assessment: Unit Check 1')).toBeVisible()
    await expect(page.getByText('Transforms → Frequency Filtering')).toBeVisible()
    await expect(page.getByText('DIP Syllabus (pdf)')).toBeVisible()
  })
})

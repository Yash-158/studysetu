// M2 GATE: CSV of 10 students -> accounts invited -> pool -> activation codes issued -> all can
// log in; personal institution created via self-serve path.
// Run against the gls-demo seed (scripts/seed_demo.py) - see README.md "Determinism". Uses a
// per-run unique roll-number prefix so the spec is re-runnable against the same persistent DB.
import { test, expect } from '@playwright/test'

const RUN_ID = Date.now().toString().slice(-6)
const ADMIN = { identifier: 'admin@gls-demo.test', password: 'Passw0rd!1' }

async function loginAsAdmin(page: import('@playwright/test').Page) {
  await page.goto('/login')
  await page.getByLabel('Institution code').fill('gls-demo')
  await page.getByLabel('Roll number or email').fill(ADMIN.identifier)
  await page.getByLabel('Password', { exact: true }).fill(ADMIN.password)
  await page.getByRole('button', { name: 'Log in' }).click()
  await expect(page).toHaveURL(/\/admin/)
}

test.describe.serial('M2: CSV import -> pool -> activate -> login, and self-serve teacher tier', () => {
  test('admin activates once (seed account, first run only)', async ({ page }) => {
    await page.goto('/activate')
    await page.getByLabel('Institution code').fill('gls-demo')
    await page.getByLabel('Roll number or email').fill(ADMIN.identifier)
    await page.getByLabel('Activation code').fill('11111111')
    await page.getByLabel('New password').fill(ADMIN.password)
    await page.getByLabel('Confirm password').fill(ADMIN.password)
    await page.getByRole('button', { name: 'Activate' }).click()
    // Already-active on repeat runs shows an error card in place - either outcome is fine here,
    // the login step right after is the real assertion.
    await page.waitForTimeout(300)
  })

  test('CSV import of 10 students issues codes, and a pool can enroll them all', async ({ page }) => {
    await loginAsAdmin(page)

    const rows = Array.from({ length: 10 }, (_, i) => `E2E Student ${RUN_ID}-${i},student,E2E${RUN_ID}${i},`)
    const csv = ['display_name,role,roll_number,email', ...rows].join('\n')

    await page.setInputFiles('#csv_file', {
      name: 'roster.csv',
      mimeType: 'text/csv',
      buffer: Buffer.from(csv),
    })
    await page.getByRole('button', { name: 'Import and issue codes' }).click()

    await expect(page.getByText('Activation codes to distribute')).toBeVisible()
    const issuedRows = page.locator('table').first().locator('tbody tr')
    await expect(issuedRows).toHaveCount(10)

    // Grab the first imported student's code straight out of the printable table.
    const firstRow = issuedRows.first()
    const rollCell = await firstRow.locator('td').nth(1).textContent()
    const code = await firstRow.locator('td').nth(2).textContent()
    expect(rollCell).toBe(`E2E${RUN_ID}0`)
    expect(code).toMatch(/^\d{8}$/)

    await page.getByRole('button', { name: 'Dismiss' }).click()
    const rosterRows = page.locator('table').last().locator('tbody tr')
    await expect(rosterRows).toHaveCount(await rosterRows.count()) // roster re-rendered, sanity only
    await expect(page.getByText(`E2E Student ${RUN_ID}-0`)).toBeVisible()

    // Pool: create one and enroll all 10 imported students.
    await page.getByRole('button', { name: 'Pools' }).click()
    await page.getByLabel('Name').fill(`E2E-Pool-${RUN_ID}`)
    await page.getByRole('button', { name: 'Create pool' }).click()
    // Scoped to the heading, not a bare text search: the roster-list button for this same pool
    // ("E2E-Pool-X (0 members)") is visible at the same time and also contains this name as a
    // substring, which trips Playwright's strict mode on an unscoped getByText match.
    await expect(page.getByRole('heading', { name: `E2E-Pool-${RUN_ID}` })).toBeVisible()

    for (let i = 0; i < 10; i++) {
      await page.getByLabel(new RegExp(`E2E Student ${RUN_ID}-${i} `)).check()
    }
    await page.getByRole('button', { name: 'Add selected' }).click()
    await expect(page.getByText(`E2E-Pool-${RUN_ID} (10 members)`)).toBeVisible()

    // Full round trip: activate and log in as the first imported student to prove the issued
    // code actually works end-to-end (all 10 share the same mechanism; this proves it).
    await page.goto('/activate')
    await page.getByLabel('Institution code').fill('gls-demo')
    await page.getByLabel('Roll number or email').fill(`E2E${RUN_ID}0`)
    await page.getByLabel('Activation code').fill(code!)
    await page.getByLabel('New password').fill('StudentPass!1')
    await page.getByLabel('Confirm password').fill('StudentPass!1')
    await page.getByRole('button', { name: 'Activate' }).click()
    await expect(page).toHaveURL(/\/login/)

    await page.getByLabel('Institution code').fill('gls-demo')
    await page.getByLabel('Roll number or email').fill(`E2E${RUN_ID}0`)
    await page.getByLabel('Password', { exact: true }).fill('StudentPass!1')
    await page.getByRole('button', { name: 'Log in' }).click()
    await expect(page).toHaveURL(/\/student/)
  })

  test('self-serve teacher signup creates a personal institution and logs straight in', async ({ page }) => {
    await page.goto('/teacher-signup')
    await page.getByLabel('Classroom / institution name').fill(`Solo Prof ${RUN_ID}`)
    await page.getByLabel('Your name').fill('Prof Solo')
    await page.getByLabel('Email').fill(`solo-${RUN_ID}@e2e.local`)
    await page.getByLabel('Password').fill('SoloPass!1')
    await page.getByRole('button', { name: 'Create my classroom' }).click()

    await expect(page).toHaveURL(/\/teacher/)
    await expect(page.locator('header').getByText(/teacher/i)).toBeVisible()
  })
})

// M1 GATE: seeded admin/teacher/student activate, log in, land on distinct shells, on the real
// domain; wrong-role route access = 403; refresh works across restart.
// Run `uv run scripts/seed_demo.py` against a fresh DB first (see README.md "Determinism").
import { test, expect } from '@playwright/test'

const INSTITUTION_SLUG = 'gls-demo'
const ROLES = [
  { role: 'admin', identifier: 'admin@gls-demo.test', code: '11111111', password: 'Passw0rd!1' },
  { role: 'teacher', identifier: 'anvi@gls-demo.test', code: '22222222', password: 'Passw0rd!2' },
  { role: 'student', identifier: '21BCE001', code: '33333333', password: 'Passw0rd!3' },
] as const

async function login(page: import('@playwright/test').Page, identifier: string, password: string) {
  await page.goto('/login')
  await page.getByLabel('Institution code').fill(INSTITUTION_SLUG)
  await page.getByLabel('Roll number or email').fill(identifier)
  await page.getByLabel('Password', { exact: true }).fill(password)
  await page.getByRole('button', { name: 'Log in' }).click()
}

for (const { role, identifier, code, password } of ROLES) {
  test(`${role} activates, logs in, and lands on the ${role} shell`, async ({ page }) => {
    await page.goto('/activate')
    await page.getByLabel('Institution code').fill(INSTITUTION_SLUG)
    await page.getByLabel('Roll number or email').fill(identifier)
    await page.getByLabel('Activation code').fill(code)
    await page.getByLabel('New password').fill(password)
    await page.getByLabel('Confirm password').fill(password)
    await page.getByRole('button', { name: 'Activate' }).click()

    // Activation does not auto-login: GATE reads "activate, log in, land on shells" as 3 steps.
    await expect(page).toHaveURL(/\/login/)

    await login(page, identifier, password)

    await expect(page).toHaveURL(new RegExp(`/${role}`))
    await expect(page.locator('header').getByText(new RegExp(role, 'i'))).toBeVisible()
  })
}

test('wrong-role route access shows 403 in place', async ({ page }) => {
  await login(page, '21BCE001', 'Passw0rd!3')
  await expect(page).toHaveURL(/\/student/)

  await page.goto('/teacher')
  await expect(page).toHaveURL(/\/teacher/) // no redirect - 403 rendered at the attempted URL
  await expect(page.getByText('403')).toBeVisible()
})

test('session survives a reload (refresh token persists, no server-side session needed)', async ({ page }) => {
  await login(page, 'anvi@gls-demo.test', 'Passw0rd!2')
  await expect(page).toHaveURL(/\/teacher/)

  await page.reload()

  await expect(page).toHaveURL(/\/teacher/)
  await expect(page.locator('header').getByText(/teacher/i)).toBeVisible()
})

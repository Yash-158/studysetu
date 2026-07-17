// Milestone-gate specs run against a locally running stack (api on :8000, web on :5173) with
// scripts/seed_demo.py already applied - see README.md "Determinism". Not wired into CI yet
// (full e2e-in-CI is M11's "e2e suite green" GATE); run manually: `pnpm -C e2e test`.
import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: '.',
  fullyParallel: false,
  retries: 0,
  use: {
    baseURL: process.env.E2E_BASE_URL ?? 'http://localhost:5173',
    trace: 'retain-on-failure',
  },
})

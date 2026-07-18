// Milestone-gate specs run against a locally running stack (api on :8000, web on :5173) with
// scripts/seed_demo.py already applied - see README.md "Determinism". Not wired into CI yet
// (full e2e-in-CI is M11's "e2e suite green" GATE); run manually: `pnpm -C e2e test`.
import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: '.',
  fullyParallel: false,
  // fullyParallel:false only serializes tests WITHIN a file; Playwright still runs different spec
  // FILES concurrently across workers by default. Multiple specs share the same fixed seeded demo
  // accounts (anvi@gls-demo.test, 21BCE001) for their "activate once" step - running two files'
  // activation attempts in parallel races on which one wins, and the loser's UI stays on /activate
  // instead of redirecting. workers:1 serializes spec files too, matching this suite's own stated
  // Determinism goal (see README.md) at the cost of a fully sequential (not parallel) local run.
  workers: 1,
  retries: 0,
  use: {
    baseURL: process.env.E2E_BASE_URL ?? 'http://localhost:5173',
    trace: 'retain-on-failure',
  },
})

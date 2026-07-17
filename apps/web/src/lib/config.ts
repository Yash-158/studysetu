// THE ONLY frontend module that reads configuration (RULES.md #2).
// Runtime config from /config.json (branding, features, locales); theme tokens injected as CSS vars.
// API_BASE: build-time knob (VITE_API_BASE_URL, see apps/web/.env.production). Empty in dev: Vite proxies
// same-origin requests to the local API (vite.config.ts). Set in prod: frontend and API are on
// different subdomains (studysetu. / studysetu-api.caffeineclause.tech), so requests must be absolute.
export type AppConfig = { product?: any; branding?: any; features?: Record<string, unknown>; locales?: any }
const API_BASE = import.meta.env.VITE_API_BASE_URL ?? ''
export const apiUrl = (path: string) => `${API_BASE}${path}`
let cached: AppConfig | null = null
export async function loadConfig(): Promise<AppConfig> {
  if (cached) return cached
  const res = await fetch(apiUrl('/config.json'))
  cached = (await res.json()) as AppConfig
  const colors = cached.branding?.colors ?? {}
  for (const [k, v] of Object.entries(colors)) document.documentElement.style.setProperty(`--color-${k}`, String(v))
  return cached
}
export const getConfig = () => cached ?? {}

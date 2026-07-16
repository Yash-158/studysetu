// THE ONLY frontend module that reads configuration (RULES.md #2).
// Runtime config from /config.json (branding, features, locales); theme tokens injected as CSS vars.
export type AppConfig = { product?: any; branding?: any; features?: Record<string, unknown>; locales?: any }
let cached: AppConfig | null = null
export async function loadConfig(): Promise<AppConfig> {
  if (cached) return cached
  const res = await fetch('/config.json')
  cached = (await res.json()) as AppConfig
  const colors = cached.branding?.colors ?? {}
  for (const [k, v] of Object.entries(colors)) document.documentElement.style.setProperty(`--color-${k}`, String(v))
  return cached
}
export const getConfig = () => cached ?? {}

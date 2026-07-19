// THE ONLY frontend module that reads configuration (RULES.md #2).
// Runtime config from /config.json (branding, features, locales); theme tokens injected as CSS vars.
// API_BASE: build-time knob (VITE_API_BASE_URL, see apps/web/.env.production). Empty in dev: Vite proxies
// same-origin requests to the local API (vite.config.ts). Set in prod: frontend and API are on
// different subdomains (studysetu. / studysetu-api.caffeineclause.tech), so requests must be absolute.
//
// Token resolution (docs/DESIGN.md): config/app.yaml ships ALL 8 palettes + both typography
// pairings in one /config.json response; THIS module picks the active one and injects the full
// CSS variable set. Switching active_palette/active_typography in app.yaml is a single value
// change - no code here needs to change for that to take effect.
export type AppConfig = { product?: any; branding?: any; features?: Record<string, unknown>; locales?: any }
const API_BASE = import.meta.env.VITE_API_BASE_URL ?? ''
export const apiUrl = (path: string) => `${API_BASE}${path}`
let cached: AppConfig | null = null

function setVar(name: string, value: unknown) {
  document.documentElement.style.setProperty(name, String(value))
}

function applyBranding(branding: any) {
  if (!branding) return

  const palette = branding.palettes?.[branding.active_palette]
  if (palette) {
    setVar('--color-primary', palette.colors.primary)
    setVar('--color-secondary', palette.colors.secondary)
    setVar('--color-accent', palette.colors.accent)
    setVar('--color-background', palette.colors.background)
    setVar('--color-button-primary-bg', palette.button_primary_bg)
    // Universal, not palette-dependent: button_primary_bg is chosen per-palette specifically so
    // white text always clears WCAG AA against it (docs/DESIGN.md's contrast check) - still a
    // named token, not a hardcoded #fff in component CSS.
    setVar('--color-on-primary', '#FFFFFF')

    const track = branding.neutral_tracks?.[palette.neutral_track] ?? {}
    for (const [step, hex] of Object.entries(track)) setVar(`--color-neutral-${step}`, hex)
    setVar('--color-ink', track['900'])

    // Back-compat aliases for the pre-token-system var names still used across existing screens
    // (Phase 5 migrates these away; kept here so nothing breaks mid-migration).
    setVar('--color-bg', palette.colors.background)
  }

  const status = branding.status
  if (status) {
    for (const [k, v] of Object.entries(status)) setVar(`--color-${k.replace(/_/g, '-')}`, v)
    setVar('--color-attention', status.warning)
    setVar('--color-mastery', status.success)
    setVar('--color-danger', status.error)
  }

  const typography = branding.typography?.[branding.active_typography]
  if (typography) {
    setVar('--font-body', `'${typography.body}', sans-serif`)
    setVar('--font-display', `'${typography.display}', sans-serif`)
    if (typography.google_fonts_url && !document.querySelector(`link[href="${typography.google_fonts_url}"]`)) {
      const link = document.createElement('link')
      link.rel = 'stylesheet'
      link.href = typography.google_fonts_url
      document.head.appendChild(link)
    }
  }

  for (const [k, v] of Object.entries(branding.spacing ?? {})) setVar(`--space-${k}`, v)
  for (const [k, v] of Object.entries(branding.radius ?? {})) setVar(`--radius-${k}`, v)
  for (const [k, v] of Object.entries(branding.shadow ?? {})) setVar(`--shadow-${k}`, v)
}

export async function loadConfig(): Promise<AppConfig> {
  if (cached) return cached
  const res = await fetch(apiUrl('/config.json'))
  cached = (await res.json()) as AppConfig
  applyBranding(cached.branding)
  return cached
}
export const getConfig = () => cached ?? {}

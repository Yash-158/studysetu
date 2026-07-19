// Dev-only design comparison tool. NOT part of the real app: no backend calls, no auth, no data
// fetching. Reachable only at /__design-preview, and that route is registered only when
// import.meta.env.DEV is true (see apps/app/App.tsx) - it does not exist in the production
// bundle at all, not merely "unlinked". Never import this file from production code.
import { useState } from 'react'
import { NEUTRAL_TRACKS, PALETTES, STATUS, TYPOGRAPHY_PAIRINGS, type Palette, type TypographyPairing } from './palettes'
import './design-preview.css'

function paletteToVars(palette: Palette, typography: TypographyPairing): React.CSSProperties {
  const neutral = NEUTRAL_TRACKS[palette.neutralTrack]
  return {
    '--color-primary': palette.colors.primary,
    '--color-secondary': palette.colors.secondary,
    '--color-accent': palette.colors.accent,
    '--color-background': palette.colors.background,
    '--color-button-primary-bg': palette.buttonPrimaryBg,
    '--color-surface': STATUS.surface,
    '--color-success': STATUS.success,
    '--color-warning': STATUS.warning,
    '--color-error': STATUS.error,
    '--color-success-text': STATUS.successText,
    '--color-warning-text': STATUS.warningText,
    '--color-error-text': STATUS.errorText,
    '--color-neutral-900': neutral['900'],
    '--color-neutral-700': neutral['700'],
    '--color-neutral-500': neutral['500'],
    '--color-neutral-300': neutral['300'],
    '--color-neutral-200': neutral['200'],
    '--color-neutral-100': neutral['100'],
    '--radius-sm': '8px', '--radius-md': '12px', '--radius-lg': '16px', '--radius-full': '999px',
    '--shadow-sm': '0 1px 2px rgba(0,0,0,0.06)',
    '--shadow-md': '0 1px 2px rgba(0,0,0,0.06), 0 1px 6px rgba(0,0,0,0.04)',
    '--dp-font-body': `'${typography.body}', sans-serif`,
    '--dp-font-display': `'${typography.display}', sans-serif`,
  } as React.CSSProperties
}

function loadFontsOnce(url: string) {
  if (document.querySelector(`link[href="${url}"]`)) return
  const link = document.createElement('link')
  link.rel = 'stylesheet'
  link.href = url
  document.head.appendChild(link)
}

export function DesignPreview() {
  const [paletteId, setPaletteId] = useState(PALETTES[0].id)
  const [typographyId, setTypographyId] = useState(TYPOGRAPHY_PAIRINGS[0].id)
  const palette = PALETTES.find((p) => p.id === paletteId)!
  const typography = TYPOGRAPHY_PAIRINGS.find((t) => t.id === typographyId)!
  loadFontsOnce(typography.googleFontsUrl)

  return (
    <div className="dp-page">
      <div className="dp-toolbar">
        <strong>Design Preview (dev only)</strong>
        <label>
          Palette:{' '}
          <select value={paletteId} onChange={(e) => setPaletteId(e.target.value as typeof paletteId)}>
            {PALETTES.map((p) => (
              <option key={p.id} value={p.id}>{p.name}{p.usesButtonFallback ? ' *' : ''}</option>
            ))}
          </select>
        </label>
        <label>
          Typography:{' '}
          <select value={typographyId} onChange={(e) => setTypographyId(e.target.value as typeof typographyId)}>
            {TYPOGRAPHY_PAIRINGS.map((t) => (
              <option key={t.id} value={t.id}>{t.name}</option>
            ))}
          </select>
        </label>
        <span>
          primary <code>{palette.colors.primary}</code> · secondary <code>{palette.colors.secondary}</code> · accent <code>{palette.colors.accent}</code>
        </span>
        <span className="dp-swatches">
          <span className="dp-swatch" style={{ background: palette.colors.primary }} title="primary" />
          <span className="dp-swatch" style={{ background: palette.colors.secondary }} title="secondary" />
          <span className="dp-swatch" style={{ background: palette.colors.accent }} title="accent" />
        </span>
        <span>Recommended logo colors: <code>{palette.logoColors[0]}</code>, <code>{palette.logoColors[1]}</code> (recommendation only, no logo generated)</span>
        {palette.usesButtonFallback && (
          <span className="dp-fallback-note" title="This palette's given primary fails WCAG AA (4.5:1) for white button text, so solid buttons use this palette's own secondary color instead - a deliberate accessibility fallback, not a rendering bug.">
            * button uses secondary color as fill (primary fails AA for white text - see docs/DESIGN.md)
          </span>
        )}
      </div>

      <div className="dp-stage" style={paletteToVars(palette, typography)}>
        <section>
          <p className="dp-section-label">Navbar</p>
          <div className="dp-navbar">
            <span className="dp-navbar-brand">StudySetu</span>
            <nav className="dp-navbar-links">
              <span>Features</span><span>How It Works</span><span>Pricing</span>
            </nav>
            <button className="dp-btn dp-btn-primary">Get Started</button>
          </div>
        </section>

        <section>
          <p className="dp-section-label">Hero</p>
          <div className="dp-hero">
            <h1>Every student, personally understood.</h1>
            <p>StudySetu diagnoses what a student actually knows, then teaches the gap - not the whole chapter again.</p>
            <div className="dp-button-row" style={{ justifyContent: 'center' }}>
              <button className="dp-btn dp-btn-primary">Start free</button>
              <button className="dp-btn dp-btn-secondary">See how it works</button>
            </div>
          </div>
        </section>

        <section>
          <p className="dp-section-label">Buttons (3 hierarchy tiers)</p>
          <div className="dp-button-row">
            <button className="dp-btn dp-btn-primary">Primary action</button>
            <button className="dp-btn dp-btn-secondary">Secondary action</button>
            <button className="dp-btn dp-btn-tertiary">Tertiary link</button>
          </div>
        </section>

        <section>
          <p className="dp-section-label">Cards</p>
          <div className="dp-card-row">
            <div className="dp-card">
              <h3>Diagnostic Engine</h3>
              <p>A 5-question probe, drawn from a teacher-reviewed bank, finds exactly what a student is shaky on.</p>
            </div>
            <div className="dp-card">
              <h3>Mastery Tracking</h3>
              <p>BKT-modeled mastery per topic, with prerequisite-aware revision injected automatically.</p>
            </div>
          </div>
        </section>

        <section>
          <p className="dp-section-label">Data table row</p>
          <table className="dp-table">
            <thead><tr><th>Student</th><th>Topic</th><th>Mastery</th></tr></thead>
            <tbody>
              <tr><td>Yash</td><td>Frequency Filtering</td><td>68%</td></tr>
              <tr><td>Anvi</td><td>Transforms</td><td>91%</td></tr>
            </tbody>
          </table>
        </section>

        <section>
          <p className="dp-section-label">Form input</p>
          <div className="dp-field">
            <label htmlFor="dp-demo-input">Institution code</label>
            <input id="dp-demo-input" placeholder="gls-demo" />
          </div>
        </section>

        <section>
          <p className="dp-section-label">Progress / mastery bar</p>
          <div className="dp-progress-track"><div className="dp-progress-fill" style={{ width: '65%' }} /></div>
        </section>

        <section>
          <p className="dp-section-label">Alert</p>
          <div className="dp-alert">3 students joined pool "CSE-3A" after you enrolled it. Add them to this subject?</div>
        </section>

        <section>
          <p className="dp-section-label">Badges (status pills - uses the AA-safe *_text tokens, not the raw swatch)</p>
          <div className="dp-badge-row">
            <span className="dp-badge dp-badge-success">approved</span>
            <span className="dp-badge dp-badge-warning">draft</span>
            <span className="dp-badge dp-badge-error">flagged</span>
          </div>
        </section>
      </div>
    </div>
  )
}

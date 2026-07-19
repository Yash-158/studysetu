> StudySetu design law: minimal teacher UI (one form per creation act, no wizard >1 step: FEATURE_EXPLANATION S2); mentor framing over surveillance framing on all student-facing analytics; branding tokens come ONLY from config/app.yaml via CSS variables.

# DESIGN.md - Visual Constitution
Purpose: the design system as enforceable tokens and principles. All tokens live in config/app.yaml (branding is configuration); this doc records values + rationale + how to work with the system. Page mockups do NOT live here (Figma frames, linked in MEMORY.md).

**Status:** design-token-system foundation work (done between M4 and M5, not a milestone itself - see docs/MEMORY.md) made this document authoritative. Everything below reflects the real, shipped mechanism, not aspiration - grep the codebase before assuming a claim here has drifted.

## Personality
Warm, confident, non-childish (Grade 8 users reject babyish UI). Duolingo discipline, Linear polish. Nothing that lags a low-end Android.

## Token architecture
Three layers, config/app.yaml -> apps/web/src/lib/config.ts -> CSS custom properties on `:root`. No component ever hardcodes a hex value, a font-family string naming a specific typeface, or (as of the design-token-system work) a spacing/radius/shadow pixel value that has a matching scale step.

1. **Primitive**: the raw palette swatches (`branding.palettes.palette_N.colors.{primary,secondary,accent,background}`), the shared status swatches (`branding.status.{success,warning,error}`), and the two neutral scales (`branding.neutral_tracks.{warm,cool}`, six steps 900->100 darkest->lightest).
2. **Semantic**: purpose aliases resolved by `config.ts` from the *active* palette/typography - `--color-primary`, `--color-background`, `--color-surface`, `--color-success` / `-warning` / `-error`, `--color-success-text` / `-warning-text` / `-error-text` (see "Status colors and the contrast fix" below), `--color-neutral-900`..`-100`, `--font-body`, `--font-display`, `--space-xs`..`-3xl`, `--radius-sm`..`-full`, `--shadow-sm`..`-lg`.
3. **Component**: values that exist because ONE component's contrast requirement demands something other than the raw semantic value - currently just `--color-button-primary-bg` (see below) and `--color-on-primary` (a fixed `#FFFFFF`, injected as a named token rather than hardcoded in component CSS, since every palette's `button_primary_bg` is specifically chosen to keep white text AA-safe against it).

`apps/web/src/lib/config.ts`'s `applyBranding()` is the ONLY place these are computed - RULES.md #2 (config read ONLY in `core/config.py` + `config.ts`) covers this: the palette catalog and resolution logic both count as configuration, not business logic, which is why `core/config.py`'s pydantic schema was extended for it (schema/validation only - see docs/ARCHITECTURE.md ADR-012).

## The active_palette / active_typography mechanism
`config/app.yaml`'s `branding` block ships ALL 8 palettes and BOTH typography pairings in one `/config.json` response; `branding.active_palette` and `branding.active_typography` name which one is live. **Changing either is a single YAML value change** - no code anywhere reads a specific palette or pairing by name; `config.ts` always resolves `branding.palettes[branding.active_palette]` and `branding.typography[branding.active_typography]` generically. To rebrand or swap the type pairing: edit those two keys, redeploy, done.

Typography loads dynamically: `config.ts` injects a single `<link>` for the ACTIVE pairing's Google Fonts URL only, the first time `applyBranding()` runs - the inactive pairing's font is never fetched by the real app. (The dev-only Design Preview page, below, loads whichever pairing is currently selected in its own switcher, independently of the real app's config.)

## The 8 palettes
All 8 exist in `config/app.yaml` today; only one is "active" in production at a time. WCAG AA (4.5:1 for text, checked directly - not eyeballed) was run against every palette's key pairs before these were committed (docs/MEMORY.md has the full finding). `button_primary_bg` differs from `primary` for palettes 6/7/8 - their given `primary` fails AA for white text, so solid buttons fall back to that same palette's own `secondary` color instead (5.9-10.95:1). This is visible on the Design Preview page as an explicit toolbar note when one of those three is selected - not a rendering bug.

| Palette | Name | Primary | Secondary | Accent | Background | button_primary_bg | Neutral track | Logo colors (recommended) |
|---|---|---|---|---|---|---|---|---|
| palette_1 | Academic Trust (**default**) | #4F46E5 | #1E3A8A | #F59E0B | #FAFAF9 | #4F46E5 | warm | #4F46E5, #F59E0B |
| palette_2 | Terracotta Scholar | #3B5BDB | #1A2E5C | #E8590C | #FDFBF7 | #3B5BDB | warm | #3B5BDB, #E8590C |
| palette_3 | Forest Focus | #0F766E | #134E4A | #65A30D | #F7FDFB | #0F766E | cool | #0F766E, #65A30D |
| palette_4 | Midnight Study | #1E3A8A | #0F172A | #38BDF8 | #F8FAFC | #1E3A8A | cool | #1E3A8A, #38BDF8 |
| palette_5 | Coral Momentum | #2563EB | #1E3A8A | #FB7185 | #FAFAFA | #2563EB | cool | #2563EB, #FB7185 |
| palette_6 | Slate Professional | #3B82F6 | #334155 | #8B5CF6 | #F9FAFB | **#334155** (fallback) | cool | #3B82F6, #8B5CF6 |
| palette_7 | Violet Insight | #6366F1 | #4C1D95 | #22D3EE | #FAFAFF | **#4C1D95** (fallback) | cool | #6366F1, #22D3EE |
| palette_8 | Sunrise Clarity | #0EA5E9 | #0369A1 | #FB923C | #F0F9FF | **#0369A1** (fallback) | cool | #0EA5E9, #FB923C |

Neutral tracks (six steps, 900 darkest -> 100 lightest):
- **warm** (stone): 900 `#1C1917` · 700 `#44403C` · 500 `#78716C` · 300 `#D6D3D1` · 200 `#E7E5E4` · 100 `#F5F5F4`
- **cool** (slate): 900 `#0F172A` · 700 `#334155` · 500 `#64748B` · 300 `#CBD5E1` · 200 `#E2E8F0` · 100 `#F1F5F9`

## Status colors and the contrast fix
Shared across every palette: success `#10B981`, warning `#F59E0B`, error `#EF4444`, surface `#FFFFFF`.

**Real, pre-existing bug found and fixed during this work** (not hypothetical - see docs/MEMORY.md's Known Limitations): the raw swatches above, used directly as TEXT color on a light tint (the `.ss-status-pill` pattern - draft/approved/flagged labels across the teacher and admin screens, and `.ss-forbidden`, the 403 page heading), fail WCAG AA badly (~2.1-3.6:1 measured). Separately-contrast-checked darker variants exist for exactly this use and pass comfortably (5.3-6.2:1 against the lightest of the 8 backgrounds): `success_text` `#047857`, `warning_text` `#B45309`, `error_text` `#B91C1C`. **Rule: any small colored TEXT on a light/tinted background uses the `*_text` token, never the raw swatch.** The raw swatch stays correct for tint backgrounds, borders, icons, and anywhere else contrast isn't a small-text concern.

## Typography
Two pairings, config-driven, switched via `active_typography`:
- **pairing_1 (default): Lexend + Space Grotesk.** Lexend for body (readability/dyslexia-friendly, per the original brand personality call), Space Grotesk for display/headings (confident, slightly technical).
- **pairing_2: Karla + Fraunces.** A warmer, more editorial contrast option - Karla is a clean humanist body face, Fraunces is a characterful serif for display, for a "premium journal" feel rather than Space Grotesk's techy energy. Compare both live on the Design Preview page before switching the default.

Scale (unchanged from the original brand call, still real): 14/16/20/25/31/39, 1.25 ratio. Body >=16px on mobile.

## Spacing, radius, shadow
Config-driven scales (`branding.spacing`/`radius`/`shadow` in app.yaml), injected as `--space-*`/`--radius-*`/`--shadow-*`:
- **Spacing**: xs `4px` · sm `8px` · md `16px` · lg `24px` · xl `32px` · 2xl `48px` · 3xl `64px`
- **Radius**: sm `8px` (controls) · md `12px` (cards) · lg `16px` (hero/featured surfaces) · full `999px` (pills)
- **Shadow**: sm (subtle, single-layer) · md (2-layer, the default card shadow) · lg (featured/elevated surfaces)

**Not every pixel value in the app maps onto this scale, and that's a deliberate, recorded set of exceptions, not an oversight** - forcing a value that doesn't fit onto the nearest step would visibly shift a layout, which the migration that adopted this scale (docs/MEMORY.md, Phase 5 of the design-token-system work) was explicitly not supposed to do. Known exceptions, each commented inline in `apps/web/src/styles/index.css`: `.ss-stack-tight`'s 6px gap, `.ss-field input/textarea`'s 10px/12px padding, `.ss-button`'s 10px horizontal padding, `.ss-table` cell padding's 10px half, `.ss-banner`'s 12px gap. One value is a **deliberate non-token constant, not a missed migration**: `.ss-button`'s `min-height: 44px` is the WCAG AA tap-target minimum (see Accessibility below) - a fixed accessibility invariant, not a themed spacing choice, and must never be pulled onto the spacing scale even if a future scale happens to gain a 44-ish step.

## Logo
Config path: `branding.logo.path` (`/brand/logo.png`, served from `apps/web/public/brand/`). The `Logo` component (`components/Logo.tsx`) renders that path and falls back to a text wordmark - in the product's display font, primary color - if the file doesn't exist yet or an `<img>` load ever fails for any other reason (`onError`-driven, not just a missing-path check). **No logo file has been generated as of this work** - the directory is reserved (`.gitkeep`) and documented here for whoever creates one.

**Export format: transparent PNG, not white background.** A baked-in white background breaks on any non-white surface - the dark footer already shipped on the landing page, a future colored section header, a future dark mode. Transparent composites correctly everywhere a white-background export would need a second, differently-named file to work around. If a specific external platform later requires a white-background version, it should exist as an explicitly-named secondary export (e.g. `logo-white-bg.png`), never as the default at `/brand/logo.png`.

Drop a real file at `apps/web/public/brand/logo.png` and it appears in the navbar, both role-shell headers, and the landing page footer automatically - zero code changes, per the same config-driven mechanism as everything else here.

## Icon usage
No icon library is installed (deliberately - see "No new dependencies" below). Where the landing page needs an icon-shaped element (the three Feature cards), it uses a single Unicode glyph in a tinted, rounded square (`--color-primary` at 12% tint) rather than an SVG icon set. If the product later needs a real icon system (e.g. status glyphs beyond what a colored pill communicates), evaluate reusing an already-adopted dependency's icon set before adding a new package - none currently ships one.

## Component inventory (build once in components/, reuse everywhere)
Button, Card, **Logo** (added by this work - config-driven image with text-wordmark fallback), ProgressRing, LessonCard, OptionRow(+misconception hint slot), DoubtBubble(streaming), GraphCanvas(mode: personal|cohort), StatTile, RosterRow, ClusterChip, OfflinePill, EmptyState, Skeleton. Landing-page sections (Navbar/Hero/Features/HowItWorks/Benefits/Testimonials/Pricing/FAQ/Footer, `apps/web/src/app/landing/`) are page-specific composition, not reusable components - they were deliberately not added to `components/` since nothing else in the app currently needs a second navbar or hero.

## States doctrine
Every screen ships loading (skeleton), empty (ghost preview with explainer), error (friendly retry card, never raw errors), and offline variants. The OfflinePill is a designed object (calm, informative, becomes "Syncing N updates" on reconnect): it is a demo prop.

## Accessibility bar (WCAG AA)
Contrast >=4.5:1; focus visible; full keyboard nav; aria-live on answer feedback; tap targets >=44px; TTS button on lesson cards; labels never color-only.

**This bar is now enforced with real contrast math, not eyeballed** - every palette's key text/background/button pairs were checked with the standard WCAG relative-luminance formula (see docs/MEMORY.md for the exact findings) before being committed, and the two real violations found (`.ss-status-pill` text, `.ss-forbidden`) were fixed via the `*_text` token layer above, not by weakening the bar. Any future palette addition or color change must be checked the same way before merging - compute relative luminance for each channel (`c<=0.03928 ? c/12.92 : ((c+0.055)/1.055)^2.4`), combine to luminance (`0.2126R+0.7152G+0.0722B`), contrast ratio `(L1+0.05)/(L2+0.05)` with L1 the lighter of the pair - 4.5:1 minimum for normal text, 3:1 for large text/UI-component-only uses like a border or an icon.

## Responsiveness
Student UI designed at 360px first; teacher UI at 1280px first (projector: also test 1024x768). Same component library, two layout shells. The landing page (public, device-unknown) is checked at both ends explicitly: nav links collapse under 720px (CTAs - Log in / Get Started - stay visible always, a real bug found and fixed during this work: the first version hid them too, leaving no visible way to log in on mobile), hero/feature/flow/testimonial/pricing grids stack to one column under 860px (720px for the footer's 4-column grid).

## Config-driven branding
Renaming the product, recoloring, or swapping fonts = editing config/app.yaml's branding block (`active_palette`, `active_typography`, or the palette/typography catalogs themselves). No component may hardcode a hex value or font name; this is enforced by convention + review today (grep before every merge: `grep -rnE "#[0-9a-fA-F]{3,6}\b"` across `apps/web/src`, expect zero hits outside `lib/config.ts` and the dev-only files below), not by an automated lint rule - `pnpm lint` has no config wired yet (pre-existing gap, unrelated to this work).

## Design Preview tool (dev-only, not part of the product)
`/__design-preview`, reachable only when `import.meta.env.DEV` is true - the route does not exist in a production build (verified against a real `vite build` + `vite preview`, not assumed). Renders every representative component type (navbar, hero, 3-tier buttons, cards, a data table row, a form input, a mastery bar, an alert, badges) with independent palette (8) and typography (2) switchers, so a full comparison happens live across the whole gallery at once, not in isolated swatches. Its palette/typography data (`apps/web/src/dev/palettes.ts`) is a **deliberately duplicated** copy of `config/app.yaml`'s catalog, not fetched - the brief for this tool required zero backend calls so it works standalone. **If a palette or typography pairing changes in `config/app.yaml`, update `palettes.ts` to match** - there is no automated sync between them.

One honest, verified caveat: Rollup still emits `DesignPreview-*.js/.css` as separate, unreferenced files in a production `dist/assets/` (normal code-splitting behavior) - unreachable via the app's navigation (confirmed: visiting `/__design-preview` on a real production build renders blank), but technically present as static files if someone already knew the exact hashed filename. Not worth extra build-config complexity to eliminate.

## Contributing to the token system
- **Add a 9th palette**: add an entry under `config/app.yaml`'s `branding.palettes`, following the existing shape exactly (`name`, `colors.{primary,secondary,accent,background}`, `button_primary_bg`, `neutral_track`, `logo_colors`). Run the WCAG contrast check above against `background`+neutral-900 text, `button_primary_bg`+white text, and (if introducing new status colors) each status color as text-on-background - if `primary` fails the button check, set `button_primary_bg` to `secondary` (or a same-hue darker shade if that also fails) rather than shipping a button nobody can read. Add the matching entry to `apps/web/src/dev/palettes.ts` so the Design Preview page can show it. No code in `config.ts` needs to change - the resolution is generic.
- **Change the active palette or typography**: edit `active_palette`/`active_typography` in `config/app.yaml`. That's the entire change.
- **Add a new spacing/radius/shadow step**: add it to the relevant block in `config/app.yaml`; `config.ts` picks up any key generically (`--space-<key>` etc.) with no code change.
- **Migrate a new screen onto tokens**: grep it for hex values and brand font-family strings first (`grep -rnE "#[0-9a-fA-F]{3,6}\b"`); replace with the matching semantic/component var. If a spacing/radius value doesn't map exactly onto the scale, leave it literal with an inline comment explaining why - do not distort a real layout to eliminate a comment.
- **Before merging any new or changed color**: run the contrast check above for every text/background pairing that color will actually render as - not just the palette's headline swatch.

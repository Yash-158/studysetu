> StudySetu design law: minimal teacher UI (one form per creation act, no wizard >1 step: FEATURE_EXPLANATION S2); mentor framing over surveillance framing on all student-facing analytics; branding tokens come ONLY from config/app.yaml via CSS variables.

# DESIGN.md - Visual Constitution
Purpose: the design system as enforceable tokens and principles. All tokens live in config/app.yaml (branding is configuration); this doc records values + rationale. Page mockups do NOT live here (Figma frames, linked in MEMORY.md).

## Personality
Warm, confident, non-childish (Grade 8 users reject babyish UI). Duolingo discipline, Linear polish. Nothing that lags a low-end Android.

## Tokens (mirrored in config/app.yaml -> CSS variables at :root)
Colors: primary indigo-600 #4F46E5; attention amber-500 #F59E0B; mastery emerald-500 #10B981; danger rose-500; bg #FAFAF7; ink #1C1917. Graph heat: red-500 -> amber-400 -> emerald-500 (always paired with icons: never color-only meaning).
Type: Lexend (body, readability/dyslexia-friendly), Space Grotesk (display numbers). Scale 1.25 ratio: 14/16/20/25/31/39. Body >=16px mobile.
Spacing: 4px base grid; radii 12px cards / 8px controls; shadows subtle 2-layer.
Motion: micro only. Node mastery pulse 400ms; card slide 250ms ease-out; ring fill spring; confetti exactly once (level-up). prefers-reduced-motion honored.

## Component inventory (build once in components/, reuse everywhere)
Button, Card, ProgressRing, LessonCard, OptionRow(+misconception hint slot), DoubtBubble(streaming), GraphCanvas(mode: personal|cohort), StatTile, RosterRow, ClusterChip, OfflinePill, EmptyState, Skeleton.

## States doctrine
Every screen ships loading (skeleton), empty (ghost preview with explainer), error (friendly retry card, never raw errors), and offline variants. The OfflinePill is a designed object (calm, informative, becomes "Syncing N updates" on reconnect): it is a demo prop.

## Accessibility bar (WCAG AA)
Contrast >=4.5:1; focus visible; full keyboard nav; aria-live on answer feedback; tap targets >=44px; TTS button on lesson cards; labels never color-only.

## Responsiveness
Student UI designed at 360px first; teacher UI at 1280px first (projector: also test 1024x768). Same component library, two layout shells.

## Config-driven branding
Renaming the product, recoloring, or swapping fonts = editing config/app.yaml branding block. No component may hardcode a hex value or font name; lint rule enforces var() usage.

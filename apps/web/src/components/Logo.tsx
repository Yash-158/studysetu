// DESIGN.md component inventory: Logo (build once, reuse everywhere - Navbar, LandingPage, and
// RoleShell all render the same brand mark). Path is config-driven (branding.logo.path,
// config/app.yaml) - dropping a real file at apps/web/public/brand/logo.png makes it appear
// everywhere with zero code changes. Until then, or if the image fails to load for any reason,
// falls back to a clean text wordmark - never a broken-image icon.
//
// size is a real prop, not a single hardcoded value: the actual logo.png is a 3000x3000 square
// (a typical high-res export) and a fixed small height that happened to match the OLD
// text-wordmark's line-height rendered it as a barely-visible speck once a real file existed -
// found via the file's real dimensions, not guessed. 'sm'/'md'/'lg' let a nav bar and a future
// hero-scale placement reasonably differ without every call site inventing its own number.
import { useState } from 'react'
import { getConfig } from '../lib/config'

export type LogoSize = 'sm' | 'md' | 'lg'

export function Logo({ className = '', size = 'md' }: { className?: string; size?: LogoSize }) {
  const [imgFailed, setImgFailed] = useState(false)
  const config = getConfig()
  const product = config.product as { name?: string } | undefined
  const logoPath = (config.branding as { logo?: { path?: string } } | undefined)?.logo?.path
  const name = product?.name ?? 'StudySetu'

  if (!logoPath || imgFailed) {
    return <span className={`ss-logo-wordmark ss-logo-wordmark-${size} ${className}`.trim()}>{name}</span>
  }
  return <img src={logoPath} alt={name} className={`ss-logo ss-logo-${size} ${className}`.trim()} onError={() => setImgFailed(true)} />
}

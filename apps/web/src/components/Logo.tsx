// DESIGN.md component inventory: Logo (build once, reuse everywhere - Navbar, LandingPage, and
// RoleShell all render the same brand mark). Path is config-driven (branding.logo.path,
// config/app.yaml) - dropping a real file at apps/web/public/brand/logo.png makes it appear
// everywhere with zero code changes. Until then, or if the image fails to load for any reason,
// falls back to a clean text wordmark - never a broken-image icon.
import { useState } from 'react'
import { getConfig } from '../lib/config'

export function Logo({ className = '' }: { className?: string }) {
  const [imgFailed, setImgFailed] = useState(false)
  const config = getConfig()
  const product = config.product as { name?: string } | undefined
  const logoPath = (config.branding as { logo?: { path?: string } } | undefined)?.logo?.path
  const name = product?.name ?? 'StudySetu'

  if (!logoPath || imgFailed) {
    return <span className={`ss-logo ss-logo-wordmark ${className}`.trim()}>{name}</span>
  }
  return <img src={logoPath} alt={name} className={`ss-logo ${className}`.trim()} onError={() => setImgFailed(true)} />
}

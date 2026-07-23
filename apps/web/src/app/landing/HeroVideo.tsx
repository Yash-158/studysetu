// Hero video embed (Phase 1 remediation). Real file goes at apps/web/public/media/hero-video.mp4
// ("StudySetu hai to mumkin hai", ~40s) - served as a plain public asset, so its absence never
// breaks the build (no import, just a runtime <video src>). A CSS-only gradient poster (brand
// tokens only, no extra image asset required) renders underneath at all times and stays visible
// until the video actually reaches a paintable frame; if the file is missing or autoplay is
// blocked, the poster is what the visitor sees - never a broken player or blank box.
import { useState } from 'react'

const VIDEO_SRC = '/media/hero-video.mp4'
const VIDEO_LABEL =
  "StudySetu hai to mumkin hai — a short look at a student's diagnostic result flowing into a personalized revision session"

export function HeroVideo() {
  const [status, setStatus] = useState<'loading' | 'ready' | 'failed'>('loading')

  return (
    <div className="landing-hero-media">
      <div className="landing-hero-poster" role="img" aria-label={VIDEO_LABEL}>
        <span className="landing-hero-poster-badge">StudySetu hai to mumkin hai</span>
      </div>
      {status !== 'failed' && (
        <video
          className="landing-hero-video"
          data-ready={status === 'ready'}
          src={VIDEO_SRC}
          autoPlay
          muted
          loop
          playsInline
          aria-label={VIDEO_LABEL}
          onCanPlay={() => setStatus('ready')}
          onError={() => setStatus('failed')}
        />
      )}
    </div>
  )
}

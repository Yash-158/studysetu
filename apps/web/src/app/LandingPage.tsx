import { Link } from 'react-router-dom'
import { Button } from '../components/Button'
import { getConfig } from '../lib/config'

export function LandingPage() {
  const config = getConfig()
  const product = config.product as { name?: string; tagline?: string } | undefined
  const selfServeEnabled = Boolean((config.features as Record<string, unknown> | undefined)?.self_serve_teacher_tier)

  return (
    <div className="ss-container">
      <div className="ss-stack">
        <h1>{product?.name ?? 'StudySetu'}</h1>
        <p>{product?.tagline}</p>
        <Link to="/login">
          <Button>Log in</Button>
        </Link>
        <p>
          First time here? <Link className="ss-link" to="/activate">Activate your account</Link>
        </p>
        {selfServeEnabled && (
          <p>
            Just you, no institution yet?{' '}
            <Link className="ss-link" to="/teacher-signup">Start your own classroom</Link>
          </p>
        )}
      </div>
    </div>
  )
}

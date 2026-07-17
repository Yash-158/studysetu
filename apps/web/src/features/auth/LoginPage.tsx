import { useState } from 'react'
import { useNavigate, useSearchParams, Link } from 'react-router-dom'
import { Button } from '../../components/Button'
import { Card } from '../../components/Card'
import { useAuth } from '../../lib/auth'

export function LoginPage() {
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const login = useAuth((s) => s.login)
  const [institutionSlug, setInstitutionSlug] = useState('gls-demo')
  const [identifier, setIdentifier] = useState(params.get('identifier') ?? '')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await login(institutionSlug, identifier, password)
      const role = useAuth.getState().user?.role
      navigate(`/${role}`, { replace: true })
    } catch (err) {
      setError((err as { message?: string }).message ?? 'Login failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="ss-container">
      <Card>
        <form className="ss-stack" onSubmit={onSubmit}>
          <h1>Log in</h1>
          {error && <p className="ss-error">{error}</p>}
          <div className="ss-field">
            <label htmlFor="institution_slug">Institution code</label>
            <input id="institution_slug" value={institutionSlug} onChange={(e) => setInstitutionSlug(e.target.value)} required />
          </div>
          <div className="ss-field">
            <label htmlFor="identifier">Roll number or email</label>
            <input id="identifier" value={identifier} onChange={(e) => setIdentifier(e.target.value)} required />
          </div>
          <div className="ss-field">
            <label htmlFor="password">Password</label>
            <input id="password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
          </div>
          <Button type="submit" disabled={busy}>{busy ? 'Logging in…' : 'Log in'}</Button>
          <p>
            First time here? <Link className="ss-link" to="/activate">Activate your account</Link>
          </p>
        </form>
      </Card>
    </div>
  )
}

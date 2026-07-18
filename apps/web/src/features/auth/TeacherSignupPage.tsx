import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { Button } from '../../components/Button'
import { Card } from '../../components/Card'
import { apiUrl } from '../../lib/config'
import { useAuth } from '../../lib/auth'

export function TeacherSignupPage() {
  const navigate = useNavigate()
  const [institutionName, setInstitutionName] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setBusy(true)
    try {
      const res = await fetch(apiUrl('/api/institutions/self-serve'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ institution_name: institutionName, display_name: displayName, email, password }),
      })
      if (!res.ok) {
        const body = await res.json().catch(() => null)
        throw body?.detail ?? { message: 'Signup failed' }
      }
      const data = await res.json()
      useAuth.setState({ accessToken: data.access_token, refreshToken: data.refresh_token, user: data.user, hydrated: true })
      navigate('/teacher', { replace: true })
    } catch (err) {
      setError((err as { message?: string }).message ?? 'Signup failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="ss-container">
      <Card>
        <form className="ss-stack" onSubmit={onSubmit}>
          <h1>Start your own classroom</h1>
          <p>No institution needed - this creates a personal space just for you and your students.</p>
          {error && <p className="ss-error">{error}</p>}
          <div className="ss-field">
            <label htmlFor="institution_name">Classroom / institution name</label>
            <input id="institution_name" value={institutionName} onChange={(e) => setInstitutionName(e.target.value)} required />
          </div>
          <div className="ss-field">
            <label htmlFor="display_name">Your name</label>
            <input id="display_name" value={displayName} onChange={(e) => setDisplayName(e.target.value)} required />
          </div>
          <div className="ss-field">
            <label htmlFor="signup_email">Email</label>
            <input id="signup_email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
          </div>
          <div className="ss-field">
            <label htmlFor="signup_password">Password</label>
            <input id="signup_password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
          </div>
          <Button type="submit" disabled={busy}>{busy ? 'Creating…' : 'Create my classroom'}</Button>
          <p>
            Already have an account? <Link className="ss-link" to="/login">Log in</Link>
          </p>
        </form>
      </Card>
    </div>
  )
}

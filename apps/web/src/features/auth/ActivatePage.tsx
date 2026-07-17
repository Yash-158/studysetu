import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { Button } from '../../components/Button'
import { Card } from '../../components/Card'
import { useAuth } from '../../lib/auth'

export function ActivatePage() {
  const navigate = useNavigate()
  const activate = useAuth((s) => s.activate)
  const [institutionSlug, setInstitutionSlug] = useState('gls-demo')
  const [identifier, setIdentifier] = useState('')
  const [activationCode, setActivationCode] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    if (newPassword !== confirmPassword) {
      setError('Passwords do not match')
      return
    }
    setBusy(true)
    try {
      await activate(institutionSlug, identifier, activationCode, newPassword)
      navigate(`/login?identifier=${encodeURIComponent(identifier)}`, { replace: true })
    } catch (err) {
      setError((err as { message?: string }).message ?? 'Activation failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="ss-container">
      <Card>
        <form className="ss-stack" onSubmit={onSubmit}>
          <h1>Activate your account</h1>
          <p>Use the institution code, your roll number or email, and the activation code your institution gave you.</p>
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
            <label htmlFor="activation_code">Activation code</label>
            <input id="activation_code" value={activationCode} onChange={(e) => setActivationCode(e.target.value)} required />
          </div>
          <div className="ss-field">
            <label htmlFor="new_password">New password</label>
            <input id="new_password" type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} required />
          </div>
          <div className="ss-field">
            <label htmlFor="confirm_password">Confirm password</label>
            <input id="confirm_password" type="password" value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} required />
          </div>
          <Button type="submit" disabled={busy}>{busy ? 'Activating…' : 'Activate'}</Button>
          <p>
            Already activated? <Link className="ss-link" to="/login">Log in</Link>
          </p>
        </form>
      </Card>
    </div>
  )
}

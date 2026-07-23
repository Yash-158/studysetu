import { useEffect, useState } from 'react'
import { Button } from '../../components/Button'
import { Card } from '../../components/Card'
import { type StudentDetail, flagArtifact, getStudentDetail } from './api'

// Mentor framing (DESIGN.md), same as features/timeline/TimelinePage.tsx - the teacher sees the
// identical ledger the student sees, human-readable, not a raw event_type dump.
function describe(e: StudentDetail['timeline'][number]): string {
  const topic = e.topic_title ? ` (${e.topic_title})` : ''
  switch (e.event_type) {
    case 'diagnostic_completed':
      return `Finished the probe${topic}`
    case 'session_started':
      return `Started a personalized session${topic}`
    case 'revision_injected':
      return `Got a refresher on ${e.topic_title ?? 'a topic'}`
    case 'session_completed':
      return `Completed the session${topic}`
    case 'mastery_changed':
      return `Mastery moved${topic}`
    default:
      return `${e.event_type}${topic}`
  }
}

export function StudentDetailPage({
  studentId,
  subjectId,
  misconceptionId,
  onBack,
}: {
  studentId: string
  subjectId: string
  misconceptionId?: string
  onBack: () => void
}) {
  const [detail, setDetail] = useState<StudentDetail | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  useEffect(() => {
    getStudentDetail(studentId, subjectId, misconceptionId)
      .then(setDetail)
      .catch((err) => setError((err as { message?: string }).message ?? 'Could not load this student'))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [studentId, subjectId, misconceptionId])

  async function onFlag(artifactId: string) {
    try {
      await flagArtifact(artifactId)
      setNotice('Flagged for review.')
      setDetail(await getStudentDetail(studentId, subjectId, misconceptionId))
    } catch (err) {
      setError((err as { message?: string }).message ?? 'Failed to flag this artifact')
    }
  }

  if (error) return <p className="ss-error">{error}</p>
  if (!detail) return <p>Loading…</p>

  return (
    <div className="ss-stack">
      <Button variant="ghost" onClick={onBack}>← Back</Button>
      {notice && <p>{notice}</p>}

      <Card>
        <h2>{detail.student.display_name}</h2>
        <p>{detail.student.roll_number ?? '—'} · <span className={`ss-status-pill ss-status-${detail.student.enrollment_status === 'active' ? 'active' : 'disabled'}`}>{detail.student.enrollment_status}</span></p>
      </Card>

      <Card>
        <h3>Mastery</h3>
        {detail.mastery.length === 0 && <p>No mastery recorded yet.</p>}
        {detail.mastery.map((m) => (
          <p key={m.topic_id}>{m.topic_title ?? m.topic_id}: {Math.round(m.p_known * 100)}% ({m.attempts_count} attempts)</p>
        ))}
      </Card>

      <Card>
        <h3>Exact wrong attempts{misconceptionId ? ' (this misconception)' : ''}</h3>
        {detail.wrong_attempts.length === 0 && <p>No wrong attempts recorded.</p>}
        {detail.wrong_attempts.map((w) => (
          <div key={w.attempt_id} className="ss-stack-tight" style={{ marginBottom: 'var(--space-sm)' }}>
            <p><strong>{w.item_stem}</strong></p>
            <p>Chose: {w.chosen_option_body}{w.misconception_title ? ` — misconception: ${w.misconception_title}` : ''}</p>
          </div>
        ))}
      </Card>

      <Card>
        <h3>AI artifacts this student encountered</h3>
        {detail.artifacts.length === 0 && <p>No AI-generated content yet.</p>}
        {detail.artifacts.map((a) => (
          <p key={a.id}>
            {a.artifact_type} — {a.topic_title ?? a.topic_id} — {a.model ?? 'unknown model'}{' '}
            {a.flagged ? <span className="ss-status-pill ss-status-disabled">flagged</span> : <Button variant="ghost" onClick={() => onFlag(a.id)}>Flag</Button>}
          </p>
        ))}
      </Card>

      <Card>
        <h3>Timeline</h3>
        {detail.timeline.length === 0 && <p>Nothing here yet.</p>}
        {detail.timeline.map((e) => (
          <p key={e.id}>{describe(e)} <span className="ss-status-pill">{new Date(e.occurred_at).toLocaleString()}</span></p>
        ))}
      </Card>
    </div>
  )
}

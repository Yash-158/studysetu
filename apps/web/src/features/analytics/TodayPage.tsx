import { useEffect, useState } from 'react'
import { Button } from '../../components/Button'
import { Card } from '../../components/Card'
import { type Today, getToday } from './api'

export function TodayPage({
  onViewStudent,
  onReviewTopic,
}: {
  onViewStudent: (studentId: string, subjectId: string, misconceptionId?: string) => void
  onReviewTopic: (topicId: string, topicTitle: string) => void
}) {
  const [today, setToday] = useState<Today | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    getToday()
      .then(setToday)
      .catch((err) => setError((err as { message?: string }).message ?? 'Could not load today’s signals'))
  }, [])

  if (error) return <p className="ss-error">{error}</p>
  if (!today) return <p>Loading…</p>

  return (
    <div className="ss-stack">
      <Card>
        <h2>Misconception clusters</h2>
        {today.clusters.length === 0 && <p>No cluster has crossed the alert threshold yet - nothing needs a group remediation today.</p>}
        {today.clusters.map((c) => (
          <div key={`${c.misconception_id}-${c.topic_id}`} className="ss-stack-tight" style={{ marginBottom: 'var(--space-md)' }}>
            <p>
              <strong>{c.misconception_title}</strong> — {c.topic_title} ({c.subject_title}) — {c.student_count} students
            </p>
            <p>
              {c.students.map((s, i) => (
                <span key={s.id}>
                  {i > 0 && ', '}
                  <button className="ss-link" onClick={() => onViewStudent(s.id, c.subject_id, c.misconception_id)}>{s.display_name}</button>
                </span>
              ))}
            </p>
          </div>
        ))}
      </Card>

      <Card>
        <h2>Stuck</h2>
        {today.stuck.length === 0 && <p>Nobody is currently stalled mid-diagnostic or mid-session.</p>}
        {today.stuck.map((s) => (
          <p key={`${s.student_id}-${s.topic_id}-${s.kind}`}>
            <button className="ss-link" onClick={() => onViewStudent(s.student_id, s.subject_id)}>{s.student_name}</button>{' '}
            has been stuck on {s.topic_title} ({s.kind}) for {s.stalled_minutes} min
          </p>
        ))}
      </Card>

      <Card>
        <h2>Ungraded</h2>
        {today.ungraded.length === 0 && <p>No item banks are awaiting review.</p>}
        {today.ungraded.map((u) => (
          <p key={u.topic_id}>
            {u.topic_title} ({u.subject_title}) — {u.draft_count} item{u.draft_count === 1 ? '' : 's'} awaiting review{' '}
            <Button onClick={() => onReviewTopic(u.topic_id, u.topic_title)}>Review</Button>
          </p>
        ))}
      </Card>
    </div>
  )
}

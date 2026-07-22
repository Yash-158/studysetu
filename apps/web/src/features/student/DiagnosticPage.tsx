import { useEffect, useRef, useState } from 'react'
import { Button } from '../../components/Button'
import { Card } from '../../components/Card'
import { type DiagnosticReview, type DiagnosticStart, answerDiagnostic, getDiagnosticReview, startDiagnostic } from './api'

// Neutral, deterministic - never reveals correctness mid-probe (FEATURE_EXPLANATION S3: feedback
// deferred to the end-of-probe review). Plain rotating copy, not AI-generated.
const NEUTRAL_ACKS = ['Got it.', 'Noted.', 'Thanks, recorded.', 'Got your answer.', 'Noted, moving on.']

export function DiagnosticPage({
  topicId,
  topicTitle,
  onBack,
  onStartSession,
}: {
  topicId: string
  topicTitle: string
  onBack: () => void
  onStartSession: () => void
}) {
  const [probe, setProbe] = useState<DiagnosticStart | null>(null)
  const [index, setIndex] = useState(0)
  const [ack, setAck] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [review, setReview] = useState<DiagnosticReview | null>(null)
  const [error, setError] = useState<string | null>(null)
  // Guards against a real bug, not just a StrictMode dev artifact: without it, two overlapping
  // calls to startDiagnostic (React 18 StrictMode's double-invoke in dev, or a genuine fast
  // double-render in production) create TWO diagnostic_sessions rows, and answers can split
  // across them as each POST resolves - discovered building M5's e2e spec, real for any caller.
  const startedRef = useRef(false)

  useEffect(() => {
    if (startedRef.current) return
    startedRef.current = true
    startDiagnostic(topicId)
      .then(setProbe)
      .catch((err) => setError((err as { message?: string }).message ?? 'Could not start the diagnostic'))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [topicId])

  async function onSelect(optionId: string) {
    if (!probe || submitting) return
    setSubmitting(true)
    setError(null)
    try {
      const item = probe.items[index]
      const result = await answerDiagnostic(probe.diagnostic_id, item.id, optionId)
      setAck(NEUTRAL_ACKS[index % NEUTRAL_ACKS.length])
      if (result.completed) {
        const finalReview = await getDiagnosticReview(probe.diagnostic_id)
        setReview(finalReview)
      } else {
        setIndex((i) => i + 1)
      }
    } catch (err) {
      setError((err as { message?: string }).message ?? 'Failed to record your answer')
    } finally {
      setSubmitting(false)
    }
  }

  if (error && !probe) return (
    <div className="ss-stack">
      <Button variant="ghost" onClick={onBack}>← Back to subject</Button>
      <p className="ss-error">{error}</p>
    </div>
  )

  if (review) {
    return (
      <div className="ss-stack">
        <h2>{topicTitle}: how you did</h2>
        <p>{review.score} / {review.total} correct</p>
        {review.review.map((q, i) => (
          <Card key={q.item_id}>
            <h3>Q{i + 1}. {q.stem}</h3>
            <ul>
              {q.options.map((o) => (
                <li key={o.id}>
                  {o.is_correct ? '✓ ' : ''}
                  {o.body}
                  {o.id === q.chosen_option_id && ' (your answer)'}
                </li>
              ))}
            </ul>
            <p>{q.explanation}</p>
          </Card>
        ))}
        <Card>
          <h2>Mastery</h2>
          <ul>
            {review.mastery.map((m) => (
              <li key={m.topic_id}>{m.topic_title}: {m.p_known === null ? '—' : `${Math.round(m.p_known * 100)}%`}</li>
            ))}
          </ul>
        </Card>
        <Button onClick={onStartSession}>Start my personalized session</Button>
        <Button variant="ghost" onClick={onBack}>Back to subject</Button>
      </div>
    )
  }

  if (!probe) return <p>Loading…</p>

  const item = probe.items[index]

  return (
    <div className="ss-stack">
      <Button variant="ghost" onClick={onBack}>← Back to subject</Button>
      {error && <p className="ss-error">{error}</p>}
      <p>Question {index + 1} of {probe.items.length}</p>
      {ack && <p aria-live="polite">{ack}</p>}
      <Card>
        <p><strong>{item.stem}</strong></p>
        <ul>
          {item.options.map((option) => (
            <li key={option.id}>
              <Button variant="ghost" disabled={submitting} onClick={() => onSelect(option.id)}>{option.body}</Button>
            </li>
          ))}
        </ul>
      </Card>
    </div>
  )
}

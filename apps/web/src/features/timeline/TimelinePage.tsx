import { useEffect, useState } from 'react'
import { Card } from '../../components/Card'
import { type TimelineEvent, getMyTimeline } from './api'

// Mentor framing, not surveillance framing (DESIGN.md) - short, warm, human-readable narration of
// what the ledger recorded, never raw event_type strings.
function describe(e: TimelineEvent): string {
  const topic = e.topic_title ? ` (${e.topic_title})` : ''
  switch (e.event_type) {
    case 'diagnostic_started':
      return `Started the probe${topic}`
    case 'diagnostic_answer_submitted':
      return `Answered a probe question${topic}`
    case 'diagnostic_completed':
      return `Finished the probe${topic}${typeof e.payload.score === 'number' ? ` - ${e.payload.score}/5` : ''}`
    case 'session_started':
      return `Started a personalized session${topic}`
    case 'revision_injected':
      return `Got a quick refresher on ${e.topic_title ?? 'a topic'} before moving on`
    case 'practice_answer_submitted':
      return `Practiced a question${topic}${e.payload.is_correct ? ' - got it right' : ''}`
    case 'session_completed':
      return `Completed the session${topic}`
    case 'mastery_changed': {
      const from = typeof e.payload.from === 'number' ? Math.round(e.payload.from * 100) : null
      const to = typeof e.payload.to === 'number' ? Math.round(e.payload.to * 100) : null
      return `Mastery moved${topic}${from !== null && to !== null ? `: ${from}% → ${to}%` : ''}`
    }
    default:
      return `${e.event_type}${topic}`
  }
}

export function TimelinePage() {
  const [events, setEvents] = useState<TimelineEvent[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    getMyTimeline()
      .then((r) => setEvents(r.events))
      .catch((err) => setError((err as { message?: string }).message ?? 'Could not load your timeline'))
  }, [])

  if (error) return <p className="ss-error">{error}</p>
  if (!events) return <p>Loading…</p>
  if (events.length === 0) return <p>Nothing here yet - take a diagnostic to get started.</p>

  return (
    <div className="ss-stack">
      <h2>Your timeline</h2>
      {events.map((e) => (
        <Card key={e.id}>
          <p>{describe(e)}</p>
          <p className="ss-status-pill">{new Date(e.occurred_at).toLocaleString()}</p>
        </Card>
      ))}
    </div>
  )
}

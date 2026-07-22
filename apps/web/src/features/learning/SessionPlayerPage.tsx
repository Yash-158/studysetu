import { useEffect, useRef, useState } from 'react'
import { Button } from '../../components/Button'
import { Card } from '../../components/Card'
import { type SafeOption, type SessionCard, answerPractice, completeSession, startSession } from '../student/api'

// The S16 recipe card types, flattened into a linear step list for the player - a revision card's
// nested practice_items become their own steps so navigation is uniform (one step, one screen).
type Step =
  | { kind: 'bridge'; text: string; cardIndex: number }
  | { kind: 'revision_intro'; topicTitle: string; explanation: string; cardIndex: number }
  | { kind: 'practice'; itemId: string; stem: string; options: SafeOption[]; cardIndex: number }
  | { kind: 'explanation'; text: string; cardIndex: number }
  | { kind: 'worked_example'; steps: string[]; cardIndex: number }
  | { kind: 'contrast'; misconceptionTitle: string; text: string; cardIndex: number }
  | { kind: 'summary'; bullets: string[]; cardIndex: number }
  | { kind: 'cheatsheet'; text: string; cardIndex: number }

function flatten(cards: SessionCard[]): Step[] {
  const steps: Step[] = []
  cards.forEach((card, cardIndex) => {
    if (card.type === 'bridge') steps.push({ kind: 'bridge', text: card.text, cardIndex })
    else if (card.type === 'revision') {
      steps.push({ kind: 'revision_intro', topicTitle: card.topic_title, explanation: card.explanation, cardIndex })
      for (const p of card.practice_items) {
        steps.push({ kind: 'practice', itemId: p.item_id, stem: p.stem, options: p.options, cardIndex })
      }
    } else if (card.type === 'explanation') steps.push({ kind: 'explanation', text: card.text, cardIndex })
    else if (card.type === 'worked_example') steps.push({ kind: 'worked_example', steps: card.steps, cardIndex })
    else if (card.type === 'practice') steps.push({ kind: 'practice', itemId: card.item_id, stem: card.stem, options: card.options, cardIndex })
    else if (card.type === 'contrast') steps.push({ kind: 'contrast', misconceptionTitle: card.misconception_title, text: card.text, cardIndex })
    else if (card.type === 'summary') steps.push({ kind: 'summary', bullets: card.bullets, cardIndex })
    else if (card.type === 'cheatsheet') steps.push({ kind: 'cheatsheet', text: card.text, cardIndex })
  })
  return steps
}

export function SessionPlayerPage({ topicId, topicTitle, onDone }: { topicId: string; topicTitle: string; onDone: () => void }) {
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [steps, setSteps] = useState<Step[] | null>(null)
  const [index, setIndex] = useState(0)
  const [reasoning, setReasoning] = useState<{ isCorrect: boolean; explanation: string } | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [finished, setFinished] = useState(false)
  // Same real-not-just-StrictMode guard as DiagnosticPage.tsx - the backend's ai/gateway.py has
  // its own race-safe upsert for the shared segment cache, but starting a session twice would
  // still create two separate learning_sessions rows for one diagnostic without this.
  const startedRef = useRef(false)

  useEffect(() => {
    if (startedRef.current) return
    startedRef.current = true
    startSession(topicId)
      .then((s) => {
        setSessionId(s.session_id)
        const flat = flatten(s.cards)
        setSteps(flat)
        // resume_index is a CARD index (server-side) - jump to the first flattened step whose
        // card is at or past it; a plan with nothing left to resume just opens on the last step.
        const startAt = flat.findIndex((step) => step.cardIndex >= s.resume_index)
        setIndex(startAt === -1 ? Math.max(flat.length - 1, 0) : startAt)
      })
      .catch((err) => setError((err as { message?: string }).message ?? 'Could not start your session'))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [topicId])

  async function onAnswer(itemId: string, optionId: string) {
    if (!sessionId || submitting) return
    setSubmitting(true)
    setError(null)
    try {
      const result = await answerPractice(sessionId, itemId, optionId)
      setReasoning({ isCorrect: result.is_correct, explanation: result.explanation })
    } catch (err) {
      const apiErr = err as { code?: string; message?: string }
      if (apiErr.code === 'bad_request' && apiErr.message?.includes('already answered')) {
        // Resumed mid-segment past this exact item already - move on rather than error.
        setIndex((i) => i + 1)
      } else {
        setError(apiErr.message ?? 'Failed to record your answer')
      }
    } finally {
      setSubmitting(false)
    }
  }

  async function onNext() {
    setReasoning(null)
    if (!steps) return
    if (index >= steps.length - 1) {
      if (sessionId) await completeSession(sessionId)
      setFinished(true)
    } else {
      setIndex((i) => i + 1)
    }
  }

  if (error && !steps) return <p className="ss-error">{error}</p>
  if (!steps) return <p>Loading…</p>

  if (finished) {
    return (
      <div className="ss-stack">
        <h2>{topicTitle}: session complete</h2>
        <p>Nice work - your mastery has been updated.</p>
        <Button onClick={onDone}>Done</Button>
      </div>
    )
  }

  const step = steps[index]

  return (
    <div className="ss-stack">
      {error && <p className="ss-error">{error}</p>}
      <Card>
        {step.kind === 'bridge' && <p>{step.text}</p>}
        {step.kind === 'revision_intro' && (
          <>
            <h3>Quick refresher: {step.topicTitle}</h3>
            <p>{step.explanation}</p>
          </>
        )}
        {step.kind === 'explanation' && (
          <>
            <h3>{topicTitle}</h3>
            <p>{step.text}</p>
          </>
        )}
        {step.kind === 'worked_example' && (
          <>
            <h3>Worked example</h3>
            <ol>{step.steps.map((s, i) => <li key={i}>{s}</li>)}</ol>
          </>
        )}
        {step.kind === 'contrast' && (
          <>
            <h3>About "{step.misconceptionTitle}"</h3>
            <p>{step.text}</p>
          </>
        )}
        {step.kind === 'summary' && (
          <>
            <h3>Summary</h3>
            <ul>{step.bullets.map((b, i) => <li key={i}>{b}</li>)}</ul>
          </>
        )}
        {step.kind === 'cheatsheet' && (
          <>
            <h3>Cheat sheet</h3>
            <p>{step.text}</p>
          </>
        )}
        {step.kind === 'practice' && (
          <>
            <p><strong>{step.stem}</strong></p>
            {reasoning ? (
              <p aria-live="polite">{reasoning.isCorrect ? '✓ Correct. ' : '✗ Not quite. '}{reasoning.explanation}</p>
            ) : (
              <ul>
                {step.options.map((option) => (
                  <li key={option.id}>
                    <Button variant="ghost" disabled={submitting} onClick={() => onAnswer(step.itemId, option.id)}>{option.body}</Button>
                  </li>
                ))}
              </ul>
            )}
          </>
        )}
      </Card>
      {(step.kind !== 'practice' || reasoning) && (
        <Button onClick={onNext}>{index >= steps.length - 1 ? 'Finish session' : 'Next'}</Button>
      )}
    </div>
  )
}

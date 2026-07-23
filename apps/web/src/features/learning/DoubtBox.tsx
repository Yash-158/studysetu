// M6-remediation Phase 5: topic-scoped doubt chat, added to the personalized lesson page
// (SessionPlayerPage). One question, one answer per ask - no threading (see modules/doubts.py's
// module docstring for why). Loading state reuses BankReviewPage.tsx's established
// disabled-button-label-swap pattern rather than inventing a new one; the answer reuses
// .ss-reasoning, the same "highlighted aside" treatment practice feedback already uses.
import { type FormEvent, useState } from 'react'
import { Button } from '../../components/Button'
import { Card } from '../../components/Card'
import { askDoubt } from '../student/api'

export function DoubtBox({ sessionId }: { sessionId: string }) {
  const [question, setQuestion] = useState('')
  const [answer, setAnswer] = useState<string | null>(null)
  const [asking, setAsking] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function onAsk(e: FormEvent) {
    e.preventDefault()
    const trimmed = question.trim()
    if (!trimmed || asking) return
    setAsking(true)
    setError(null)
    try {
      const result = await askDoubt(sessionId, trimmed)
      setAnswer(result.answer)
      setQuestion('')
    } catch (err) {
      setError((err as { message?: string }).message ?? 'Could not get an answer right now')
    } finally {
      setAsking(false)
    }
  }

  return (
    <Card className="ss-doubtbox">
      <form onSubmit={onAsk} className="ss-stack">
        <div className="ss-field">
          <label htmlFor="doubt-question">Ask a question about this topic</label>
          <textarea
            id="doubt-question"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="e.g. why does step 3 use a log transform?"
            rows={2}
          />
        </div>
        <Button type="submit" variant="ghost" disabled={asking || !question.trim()}>
          {asking ? 'Asking…' : 'Ask'}
        </Button>
      </form>
      {error && <p className="ss-error">{error}</p>}
      {answer && (
        <div className="ss-reasoning" aria-live="polite">
          <p>{answer}</p>
        </div>
      )}
    </Card>
  )
}

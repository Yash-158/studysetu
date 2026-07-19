import { useEffect, useState } from 'react'
import { Button } from '../../components/Button'
import { Card } from '../../components/Card'
import { type BankItem, approveAllBank, approveItem, generateBank, getBank } from './api'

const DIFFICULTY_LABEL: Record<number, string> = { [-1]: 'Easy', 0: 'Medium', 1: 'Hard' }

function statusPillClass(status: BankItem['status']): string {
  if (status === 'approved') return 'ss-status-active'
  if (status === 'draft') return 'ss-status-invited'
  return 'ss-status-disabled'
}

export function BankReviewPage({ topicId, topicTitle, onBack }: { topicId: string; topicTitle: string; onBack: () => void }) {
  const [items, setItems] = useState<BankItem[] | null>(null)
  const [generating, setGenerating] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  async function refresh() {
    const bank = await getBank(topicId)
    setItems(bank)
  }

  useEffect(() => {
    refresh()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [topicId])

  function fail(err: unknown, fallback: string) {
    setError((err as { message?: string }).message ?? fallback)
  }

  async function onGenerate() {
    setError(null)
    setNotice(null)
    setGenerating(true)
    try {
      const result = await generateBank(topicId)
      setNotice(result.cache_hit ? 'Served from cache - no new generation cost.' : `Generated ${result.items.length} items.`)
      await refresh()
    } catch (err) {
      fail(err, 'Failed to generate the item bank')
    } finally {
      setGenerating(false)
    }
  }

  async function onApprove(itemId: string) {
    setError(null)
    try {
      await approveItem(itemId)
      await refresh()
    } catch (err) {
      fail(err, 'Failed to approve item')
    }
  }

  async function onApproveAll() {
    setError(null)
    try {
      const result = await approveAllBank(topicId)
      setNotice(`Approved ${result.approved} item${result.approved === 1 ? '' : 's'}.`)
      await refresh()
    } catch (err) {
      fail(err, 'Failed to approve all')
    }
  }

  if (items === null) return <p>Loading…</p>

  const draftCount = items.filter((i) => i.status === 'draft').length

  return (
    <div className="ss-stack">
      <Button variant="ghost" onClick={onBack}>← Back to subject</Button>
      {error && <p className="ss-error">{error}</p>}
      {notice && <p>{notice}</p>}

      <Card>
        <h2>Item bank: {topicTitle}</h2>
        <p>{items.length} item{items.length === 1 ? '' : 's'} · {draftCount} awaiting review</p>
        <Button onClick={onGenerate} disabled={generating}>{generating ? 'Generating…' : items.length === 0 ? 'Generate bank' : 'Regenerate bank'}</Button>{' '}
        {draftCount > 0 && <Button onClick={onApproveAll}>Approve all</Button>}
      </Card>

      {items.length === 0 && !generating && (
        <Card>
          <p>No items yet. Generate a bank of 12-15 questions from this topic's materials.</p>
        </Card>
      )}

      {items.map((item) => (
        <Card key={item.id}>
          <p>
            <span className={`ss-status-pill ${statusPillClass(item.status)}`}>{item.status}</span>{' '}
            <span className="ss-status-pill ss-status-invited">{DIFFICULTY_LABEL[item.difficulty]}</span>
          </p>
          <p><strong>{item.stem}</strong></p>
          <ul>
            {item.options.map((option) => (
              <li key={option.id}>
                {option.is_correct ? '✓ ' : ''}{option.body}
                {option.misconception && <span> — misconception: {option.misconception.title}</span>}
              </li>
            ))}
          </ul>
          <p>{item.explanation}</p>
          {item.status === 'draft' && (
            <Button aria-label={`Approve: ${item.stem}`} onClick={() => onApprove(item.id)}>Approve</Button>
          )}
        </Card>
      ))}
    </div>
  )
}

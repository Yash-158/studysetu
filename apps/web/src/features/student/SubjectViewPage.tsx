import { useEffect, useState } from 'react'
import { Button } from '../../components/Button'
import { Card } from '../../components/Card'
import { type StudentSubjectDetail, getMySubject } from './api'

export function SubjectViewPage({
  subjectId,
  onBack,
  onSelectTopic,
}: {
  subjectId: string
  onBack: () => void
  onSelectTopic: (topicId: string, topicTitle: string) => void
}) {
  const [subject, setSubject] = useState<StudentSubjectDetail | null>(null)

  useEffect(() => {
    getMySubject(subjectId).then(setSubject)
  }, [subjectId])

  if (!subject) return <p>Loading…</p>

  const topicTitles = new Map<string, string>()
  for (const chapter of subject.chapters) {
    for (const block of chapter.blocks) {
      if (block.topic) topicTitles.set(block.topic.id, block.topic.title)
    }
  }

  return (
    <div className="ss-stack">
      <Button variant="ghost" onClick={onBack}>← Back to subjects</Button>

      <Card>
        <h2>{subject.name} {subject.code ? `(${subject.code})` : ''}</h2>
      </Card>

      <Card>
        <h2>Chapters</h2>
        {subject.chapters.map((chapter) => (
          <div key={chapter.id} style={{ marginBottom: 16 }}>
            <strong>{chapter.title}</strong>
            <ol>
              {chapter.blocks.map((block) => {
                const topic = block.block_type === 'topic' ? block.topic : undefined
                return (
                  <li key={block.id}>
                    {topic ? (
                      <Button variant="ghost" onClick={() => onSelectTopic(topic.id, topic.title)}>{topic.title}</Button>
                    ) : (
                      `Assessment: ${block.assessment?.title}`
                    )}
                  </li>
                )
              })}
            </ol>
          </div>
        ))}
      </Card>

      {subject.edges.length > 0 && (
        <Card>
          <h2>Suggested order</h2>
          <ul>
            {subject.edges.map((e) => (
              <li key={`${e.src_topic_id}-${e.dst_topic_id}`}>
                {topicTitles.get(e.src_topic_id) ?? e.src_topic_id} → {topicTitles.get(e.dst_topic_id) ?? e.dst_topic_id}
              </li>
            ))}
          </ul>
        </Card>
      )}

      <Card>
        <h2>Materials</h2>
        <ul>
          {subject.materials.map((m) => (
            <li key={m.id}>
              {m.title} ({m.kind}){' '}
              {m.readability === 'stored_only' && <span className="ss-status-pill ss-status-disabled">stored only - can't read yet</span>}
            </li>
          ))}
        </ul>
      </Card>
    </div>
  )
}

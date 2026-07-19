import { useEffect, useState } from 'react'
import { Button } from '../../components/Button'
import { Card } from '../../components/Card'
import {
  type Chapter,
  type Pool,
  type PoolDelta,
  type SubjectDetail,
  addBlock,
  attachPool,
  createChapter,
  createEdge,
  createMaterial,
  createTopic,
  deleteBlock,
  deleteEdge,
  getSubject,
  listPools,
  poolDeltas,
  publishChapter,
  reorderBlocks,
  reorderChapters,
  syncPool,
} from './api'

function move<T>(ids: T[], index: number, dir: -1 | 1): T[] {
  const next = [...ids]
  const j = index + dir
  if (j < 0 || j >= next.length) return ids
  ;[next[index], next[j]] = [next[j], next[index]]
  return next
}

export function SubjectBuilderPage({
  subjectId,
  onBack,
  onSelectTopic,
}: {
  subjectId: string
  onBack: () => void
  onSelectTopic: (topicId: string, topicTitle: string) => void
}) {
  const [subject, setSubject] = useState<SubjectDetail | null>(null)
  const [pools, setPools] = useState<Pool[]>([])
  const [deltas, setDeltas] = useState<PoolDelta[]>([])
  const [error, setError] = useState<string | null>(null)

  const [chapterTitle, setChapterTitle] = useState('')
  const [topicTitle, setTopicTitle] = useState('')
  const [edgeSrc, setEdgeSrc] = useState('')
  const [edgeDst, setEdgeDst] = useState('')
  const [selectedPool, setSelectedPool] = useState('')

  const [materialOwnerId, setMaterialOwnerId] = useState('')
  const [materialKind, setMaterialKind] = useState<'pdf' | 'note' | 'link' | 'image'>('pdf')
  const [materialTitle, setMaterialTitle] = useState('')
  const [materialUrl, setMaterialUrl] = useState('')
  const [materialBody, setMaterialBody] = useState('')
  const [materialFile, setMaterialFile] = useState<File | null>(null)

  const [blockTopicByChapter, setBlockTopicByChapter] = useState<Record<string, string>>({})
  const [assessmentTitleByChapter, setAssessmentTitleByChapter] = useState<Record<string, string>>({})

  async function refresh() {
    const [s, d] = await Promise.all([getSubject(subjectId), poolDeltas(subjectId)])
    setSubject(s)
    setDeltas(d)
    if (!materialOwnerId) setMaterialOwnerId(s.id)
  }

  useEffect(() => {
    refresh()
    listPools().then(setPools)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [subjectId])

  function fail(err: unknown, fallback: string) {
    setError((err as { message?: string }).message ?? fallback)
  }

  async function onCreateChapter(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    try {
      await createChapter(subjectId, chapterTitle)
      setChapterTitle('')
      await refresh()
    } catch (err) {
      fail(err, 'Failed to create chapter')
    }
  }

  async function onMoveChapter(chapters: Chapter[], index: number, dir: -1 | 1) {
    const ids = move(chapters.map((c) => c.id), index, dir)
    setError(null)
    try {
      await reorderChapters(subjectId, ids)
      await refresh()
    } catch (err) {
      fail(err, 'Failed to reorder chapters')
    }
  }

  async function onPublishChapter(chapterId: string) {
    setError(null)
    try {
      await publishChapter(chapterId)
      await refresh()
    } catch (err) {
      fail(err, 'Failed to publish chapter')
    }
  }

  async function onCreateTopic(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    try {
      await createTopic(subjectId, { title: topicTitle })
      setTopicTitle('')
      await refresh()
    } catch (err) {
      fail(err, 'Failed to create topic')
    }
  }

  async function onAddBlock(chapterId: string, kind: 'topic' | 'assessment') {
    setError(null)
    try {
      if (kind === 'topic') {
        const topicId = blockTopicByChapter[chapterId]
        if (!topicId) return
        await addBlock(chapterId, { block_type: 'topic', topic_id: topicId })
      } else {
        await addBlock(chapterId, { block_type: 'assessment', assessment_title: assessmentTitleByChapter[chapterId] || 'Assessment' })
      }
      await refresh()
    } catch (err) {
      fail(err, 'Failed to add block')
    }
  }

  async function onMoveBlock(chapterId: string, blocks: { id: string }[], index: number, dir: -1 | 1) {
    const ids = move(blocks.map((b) => b.id), index, dir)
    setError(null)
    try {
      await reorderBlocks(chapterId, ids)
      await refresh()
    } catch (err) {
      fail(err, 'Failed to reorder blocks')
    }
  }

  async function onDeleteBlock(chapterId: string, blockId: string) {
    setError(null)
    try {
      await deleteBlock(chapterId, blockId)
      await refresh()
    } catch (err) {
      fail(err, 'Failed to remove block')
    }
  }

  async function onCreateEdge(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    try {
      await createEdge(edgeSrc, edgeDst)
      setEdgeSrc('')
      setEdgeDst('')
      await refresh()
    } catch (err) {
      fail(err, 'Failed to create prerequisite link')
    }
  }

  async function onDeleteEdge(srcTopicId: string, dstTopicId: string) {
    setError(null)
    try {
      await deleteEdge(srcTopicId, dstTopicId)
      await refresh()
    } catch (err) {
      fail(err, 'Failed to remove link')
    }
  }

  async function onUploadMaterial(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    try {
      const form = new FormData()
      form.set('owner_type', materialOwnerId === subjectId ? 'subject' : 'chapter')
      form.set('owner_id', materialOwnerId)
      form.set('kind', materialKind)
      form.set('title', materialTitle)
      if (materialKind === 'link') form.set('url', materialUrl)
      if (materialKind === 'note') form.set('body', materialBody)
      if ((materialKind === 'pdf' || materialKind === 'image') && materialFile) form.set('file', materialFile)
      await createMaterial(form)
      setMaterialTitle('')
      setMaterialUrl('')
      setMaterialBody('')
      setMaterialFile(null)
      await refresh()
    } catch (err) {
      fail(err, 'Failed to upload material')
    }
  }

  async function onAttachPool() {
    if (!selectedPool) return
    setError(null)
    try {
      await attachPool(subjectId, selectedPool)
      await refresh()
    } catch (err) {
      fail(err, 'Failed to attach pool')
    }
  }

  async function onSyncPool(poolId: string) {
    setError(null)
    try {
      await syncPool(subjectId, poolId)
      await refresh()
    } catch (err) {
      fail(err, 'Failed to add new pool members')
    }
  }

  if (!subject) return <p>Loading…</p>

  return (
    <div className="ss-stack">
      <Button variant="ghost" onClick={onBack}>← Back to subjects</Button>
      {error && <p className="ss-error">{error}</p>}

      <Card>
        <h2>
          {subject.name} {subject.code ? `(${subject.code})` : ''}{' '}
          <span className={`ss-status-pill ss-status-${subject.status === 'draft' ? 'invited' : 'active'}`}>{subject.status}</span>
        </h2>
      </Card>

      {deltas.map((d) => (
        <Card key={d.pool_id} className="ss-banner">
          <p>
            {d.new_member_count} student{d.new_member_count === 1 ? '' : 's'} joined pool "{d.pool_name}" after you enrolled it. Add them to this subject?
          </p>
          <Button onClick={() => onSyncPool(d.pool_id)}>Add them</Button>
        </Card>
      ))}

      <Card>
        <h2>Chapters</h2>
        {subject.chapters.map((chapter, ci) => (
          <div key={chapter.id} className="ss-stack-tight" style={{ marginBottom: 16 }}>
            <div>
              <strong>{chapter.title}</strong>{' '}
              <span className={`ss-status-pill ss-status-${chapter.status === 'draft' ? 'invited' : 'active'}`}>{chapter.status}</span>{' '}
              <Button variant="ghost" onClick={() => onMoveChapter(subject.chapters, ci, -1)} disabled={ci === 0}>▲</Button>
              <Button variant="ghost" onClick={() => onMoveChapter(subject.chapters, ci, 1)} disabled={ci === subject.chapters.length - 1}>▼</Button>
              {chapter.status === 'draft' && (
                <Button aria-label={`Publish ${chapter.title}`} onClick={() => onPublishChapter(chapter.id)}>Publish</Button>
              )}
            </div>
            <ol>
              {chapter.blocks.map((block, bi) => (
                <li key={block.id}>
                  {block.block_type === 'topic' ? block.topic?.title : `Assessment: ${block.assessment?.title}`}{' '}
                  <Button variant="ghost" onClick={() => onMoveBlock(chapter.id, chapter.blocks, bi, -1)} disabled={bi === 0}>▲</Button>
                  <Button variant="ghost" onClick={() => onMoveBlock(chapter.id, chapter.blocks, bi, 1)} disabled={bi === chapter.blocks.length - 1}>▼</Button>
                  <Button variant="ghost" onClick={() => onDeleteBlock(chapter.id, block.id)}>Remove</Button>
                </li>
              ))}
            </ol>
            <div>
              <select
                aria-label={`Pick a topic for ${chapter.title}`}
                value={blockTopicByChapter[chapter.id] ?? ''}
                onChange={(e) => setBlockTopicByChapter({ ...blockTopicByChapter, [chapter.id]: e.target.value })}
              >
                <option value="">Pick a topic…</option>
                {subject.topics.map((t) => (
                  <option key={t.id} value={t.id}>{t.title}</option>
                ))}
              </select>{' '}
              <Button aria-label={`Add topic block to ${chapter.title}`} variant="ghost" onClick={() => onAddBlock(chapter.id, 'topic')}>Add topic block</Button>
              {' · '}
              <input
                aria-label={`Assessment title for ${chapter.title}`}
                placeholder="Assessment title"
                value={assessmentTitleByChapter[chapter.id] ?? ''}
                onChange={(e) => setAssessmentTitleByChapter({ ...assessmentTitleByChapter, [chapter.id]: e.target.value })}
              />{' '}
              <Button aria-label={`Add assessment placeholder to ${chapter.title}`} variant="ghost" onClick={() => onAddBlock(chapter.id, 'assessment')}>Add assessment placeholder</Button>
            </div>
          </div>
        ))}
        <form className="ss-stack" onSubmit={onCreateChapter}>
          <div className="ss-field">
            <label htmlFor="chapter_title">New chapter title</label>
            <input id="chapter_title" value={chapterTitle} onChange={(e) => setChapterTitle(e.target.value)} required />
          </div>
          <Button type="submit">Add chapter</Button>
        </form>
      </Card>

      <Card>
        <h2>Topics</h2>
        <ul>
          {subject.topics.map((t) => (
            <li key={t.id}>
              {t.title}{' '}
              <Button variant="ghost" onClick={() => onSelectTopic(t.id, t.title)}>Review bank</Button>
            </li>
          ))}
        </ul>
        <form className="ss-stack" onSubmit={onCreateTopic}>
          <div className="ss-field">
            <label htmlFor="topic_title">New topic title</label>
            <input id="topic_title" value={topicTitle} onChange={(e) => setTopicTitle(e.target.value)} required />
          </div>
          <Button type="submit">Add topic</Button>
        </form>
      </Card>

      <Card>
        <h2>Prerequisite links</h2>
        <ul>
          {subject.edges.map((e) => {
            const src = subject.topics.find((t) => t.id === e.src_topic_id)?.title ?? e.src_topic_id
            const dst = subject.topics.find((t) => t.id === e.dst_topic_id)?.title ?? e.dst_topic_id
            return (
              <li key={`${e.src_topic_id}-${e.dst_topic_id}`}>
                {src} → {dst}{' '}
                <Button variant="ghost" onClick={() => onDeleteEdge(e.src_topic_id, e.dst_topic_id)}>Remove</Button>
              </li>
            )
          })}
        </ul>
        <form className="ss-stack" onSubmit={onCreateEdge}>
          <div className="ss-field">
            <label htmlFor="edge_src">Requires (prerequisite)</label>
            <select id="edge_src" value={edgeSrc} onChange={(e) => setEdgeSrc(e.target.value)} required>
              <option value="">Pick a topic…</option>
              {subject.topics.map((t) => <option key={t.id} value={t.id}>{t.title}</option>)}
            </select>
          </div>
          <div className="ss-field">
            <label htmlFor="edge_dst">…is needed before</label>
            <select id="edge_dst" value={edgeDst} onChange={(e) => setEdgeDst(e.target.value)} required>
              <option value="">Pick a topic…</option>
              {subject.topics.map((t) => <option key={t.id} value={t.id}>{t.title}</option>)}
            </select>
          </div>
          <Button type="submit">Add link</Button>
        </form>
      </Card>

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
        <form className="ss-stack" onSubmit={onUploadMaterial}>
          <div className="ss-field">
            <label htmlFor="material_title">Title</label>
            <input id="material_title" value={materialTitle} onChange={(e) => setMaterialTitle(e.target.value)} required />
          </div>
          <div className="ss-field">
            <label htmlFor="material_kind">Kind</label>
            <select id="material_kind" value={materialKind} onChange={(e) => setMaterialKind(e.target.value as typeof materialKind)}>
              <option value="pdf">PDF</option>
              <option value="note">Note</option>
              <option value="link">Link</option>
              <option value="image">Image</option>
            </select>
          </div>
          {(materialKind === 'pdf' || materialKind === 'image') && (
            <div className="ss-field">
              <label htmlFor="material_file">File</label>
              <input id="material_file" type="file" accept={materialKind === 'pdf' ? '.pdf' : 'image/*'} onChange={(e) => setMaterialFile(e.target.files?.[0] ?? null)} required />
            </div>
          )}
          {materialKind === 'link' && (
            <div className="ss-field">
              <label htmlFor="material_url">URL</label>
              <input id="material_url" type="url" value={materialUrl} onChange={(e) => setMaterialUrl(e.target.value)} required />
            </div>
          )}
          {materialKind === 'note' && (
            <div className="ss-field">
              <label htmlFor="material_body">Note</label>
              <textarea id="material_body" value={materialBody} onChange={(e) => setMaterialBody(e.target.value)} required />
            </div>
          )}
          <Button type="submit">Upload</Button>
        </form>
      </Card>

      <Card>
        <h2>Pools</h2>
        <div>
          <select aria-label="Pick a pool" value={selectedPool} onChange={(e) => setSelectedPool(e.target.value)}>
            <option value="">Pick a pool…</option>
            {pools.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
          </select>{' '}
          <Button onClick={onAttachPool} disabled={!selectedPool}>Attach pool</Button>
        </div>
      </Card>
    </div>
  )
}

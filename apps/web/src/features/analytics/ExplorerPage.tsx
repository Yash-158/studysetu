import { type CSSProperties, useEffect, useState } from 'react'
import { Button } from '../../components/Button'
import { Card } from '../../components/Card'
import {
  type ExplorerSubject,
  type ExplorerSubjectDetail,
  type HeatGrid,
  type TopicStudent,
  getExplorerHeat,
  getExplorerSubject,
  getExplorerTopicStudents,
  listExplorerSubjects,
} from './api'

function pct(v: number | null): string {
  return v === null ? '—' : `${Math.round(v * 100)}%`
}

// Heat view: p_known interpolated from --color-error (0) to --color-success (1) - no chart
// dependency needed, color-mix does the gradient natively (same token-driven discipline as the
// rest of the app - DESIGN.md forbids hardcoded colors).
function heatStyle(p: number | null): CSSProperties {
  if (p === null) return { background: 'var(--color-neutral-200)' }
  return { background: `color-mix(in srgb, var(--color-success) ${Math.round(p * 100)}%, var(--color-error))` }
}

type View =
  | { kind: 'subjects' }
  | { kind: 'subject'; id: string; name: string }
  | { kind: 'heat'; id: string; name: string }
  | { kind: 'topic'; id: string; title: string; subjectId: string; subjectName: string }

export function ExplorerPage({ onViewStudent }: { onViewStudent: (studentId: string, subjectId: string) => void }) {
  const [view, setView] = useState<View>({ kind: 'subjects' })
  const [subjects, setSubjects] = useState<ExplorerSubject[] | null>(null)
  const [detail, setDetail] = useState<ExplorerSubjectDetail | null>(null)
  const [heat, setHeat] = useState<HeatGrid | null>(null)
  const [topicStudents, setTopicStudents] = useState<TopicStudent[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (view.kind === 'subjects') listExplorerSubjects().then(setSubjects).catch((err) => setError(err.message))
    if (view.kind === 'subject') {
      setDetail(null)
      getExplorerSubject(view.id).then(setDetail).catch((err) => setError(err.message))
    }
    if (view.kind === 'heat') {
      setHeat(null)
      getExplorerHeat(view.id).then(setHeat).catch((err) => setError(err.message))
    }
    if (view.kind === 'topic') {
      setTopicStudents(null)
      getExplorerTopicStudents(view.id).then(setTopicStudents).catch((err) => setError(err.message))
    }
  }, [view])

  if (error) return <p className="ss-error">{error}</p>

  if (view.kind === 'subjects') {
    if (!subjects) return <p>Loading…</p>
    return (
      <Card>
        <h2>Explorer</h2>
        {subjects.length === 0 && <p>No subjects yet - build one in the Subjects tab first.</p>}
        <table className="ss-table">
          <thead><tr><th>Subject</th><th>Students</th><th>Avg mastery</th><th></th></tr></thead>
          <tbody>
            {subjects.map((s) => (
              <tr key={s.id}>
                <td>{s.name}</td>
                <td>{s.student_count}</td>
                <td>{pct(s.avg_mastery)}</td>
                <td><button className="ss-link" onClick={() => setView({ kind: 'subject', id: s.id, name: s.name })}>Drill in</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    )
  }

  if (view.kind === 'subject') {
    return (
      <div className="ss-stack">
        <Button variant="ghost" onClick={() => setView({ kind: 'subjects' })}>← Subjects</Button>
        <Button onClick={() => setView({ kind: 'heat', id: view.id, name: view.name })}>Heat view</Button>
        {!detail && <p>Loading…</p>}
        {detail && detail.chapters.length === 0 && <p>No chapters yet.</p>}
        {detail?.chapters.map((chapter) => (
          <Card key={chapter.id}>
            <h3>{chapter.title}</h3>
            {chapter.topics.length === 0 && <p>No topics in this chapter yet.</p>}
            <table className="ss-table">
              <thead><tr><th>Topic</th><th>Avg mastery</th><th>Completion</th><th>Top misconceptions</th><th></th></tr></thead>
              <tbody>
                {chapter.topics.map((topic) => (
                  <tr key={topic.id}>
                    <td>{topic.title}</td>
                    <td>{pct(topic.avg_mastery)}</td>
                    <td>{pct(topic.completion_pct)}</td>
                    <td>{topic.top_misconceptions.length === 0 ? '—' : topic.top_misconceptions.map((m) => `${m.misconception_title} (${m.student_count})`).join('; ')}</td>
                    <td>
                      <button
                        className="ss-link"
                        onClick={() => setView({ kind: 'topic', id: topic.id, title: topic.title, subjectId: detail.id, subjectName: detail.name })}
                      >
                        Students
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
        ))}
      </div>
    )
  }

  if (view.kind === 'heat') {
    return (
      <div className="ss-stack">
        <Button variant="ghost" onClick={() => setView({ kind: 'subject', id: view.id, name: view.name })}>← {view.name}</Button>
        {!heat && <p>Loading…</p>}
        {heat && (heat.students.length === 0 || heat.topics.length === 0) && <p>Not enough activity yet for a heat view.</p>}
        {heat && heat.students.length > 0 && heat.topics.length > 0 && (
          <Card>
            <div style={{ overflowX: 'auto' }}>
              <table className="ss-table">
                <thead>
                  <tr>
                    <th>Student</th>
                    {heat.topics.map((t) => <th key={t.id}>{t.title}</th>)}
                  </tr>
                </thead>
                <tbody>
                  {heat.students.map((s) => (
                    <tr key={s.id}>
                      <td>{s.display_name}</td>
                      {heat.topics.map((t) => {
                        const cell = heat.cells.find((c) => c.student_id === s.id && c.topic_id === t.id)
                        return (
                          <td key={t.id} style={heatStyle(cell?.p_known ?? null)}>
                            {cell ? pct(cell.p_known) : '—'}
                          </td>
                        )
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        )}
      </div>
    )
  }

  // view.kind === 'topic'
  return (
    <div className="ss-stack">
      <Button variant="ghost" onClick={() => setView({ kind: 'subject', id: view.subjectId, name: view.subjectName })}>← {view.subjectName}</Button>
      <Card>
        <h3>{view.title}</h3>
        {!topicStudents && <p>Loading…</p>}
        {topicStudents && topicStudents.length === 0 && <p>No enrolled students yet.</p>}
        {topicStudents && topicStudents.length > 0 && (
          <table className="ss-table">
            <thead><tr><th>Student</th><th>Mastery</th><th>Attempts</th><th></th></tr></thead>
            <tbody>
              {topicStudents.map((s) => (
                <tr key={s.student_id}>
                  <td>{s.display_name}</td>
                  <td>{pct(s.p_known)}</td>
                  <td>{s.attempts_count}</td>
                  <td><button className="ss-link" onClick={() => onViewStudent(s.student_id, view.subjectId)}>View</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  )
}

import { useState } from 'react'
import { RoleShell } from '../../components/RoleShell'
import { SessionPlayerPage } from '../learning/SessionPlayerPage'
import { TimelinePage } from '../timeline/TimelinePage'
import { DiagnosticPage } from './DiagnosticPage'
import { SubjectViewPage } from './SubjectViewPage'
import { SubjectsPage } from './SubjectsPage'

type Tab = 'learn' | 'timeline'

export function StudentShell() {
  const [tab, setTab] = useState<Tab>('learn')
  const [subjectId, setSubjectId] = useState<string | null>(null)
  const [diagnosticTopic, setDiagnosticTopic] = useState<{ id: string; title: string } | null>(null)
  const [sessionTopic, setSessionTopic] = useState<{ id: string; title: string } | null>(null)

  function backToSubject() {
    setSessionTopic(null)
    setDiagnosticTopic(null)
  }

  return (
    <RoleShell roleLabel="Student">
      <div className="ss-tabs ss-no-print">
        <button className={`ss-tab ${tab === 'learn' ? 'ss-tab-active' : ''}`} onClick={() => setTab('learn')}>
          Learn
        </button>
        <button className={`ss-tab ${tab === 'timeline' ? 'ss-tab-active' : ''}`} onClick={() => setTab('timeline')}>
          My Timeline
        </button>
      </div>

      {tab === 'timeline' ? (
        <TimelinePage />
      ) : sessionTopic ? (
        <SessionPlayerPage topicId={sessionTopic.id} topicTitle={sessionTopic.title} onDone={backToSubject} />
      ) : diagnosticTopic ? (
        <DiagnosticPage
          topicId={diagnosticTopic.id}
          topicTitle={diagnosticTopic.title}
          onBack={backToSubject}
          onStartSession={() => setSessionTopic(diagnosticTopic)}
        />
      ) : subjectId ? (
        <SubjectViewPage
          subjectId={subjectId}
          onBack={() => setSubjectId(null)}
          onSelectTopic={(id, title) => setDiagnosticTopic({ id, title })}
        />
      ) : (
        <SubjectsPage onSelect={setSubjectId} />
      )}
    </RoleShell>
  )
}

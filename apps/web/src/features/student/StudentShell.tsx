import { useState } from 'react'
import { RoleShell } from '../../components/RoleShell'
import { DiagnosticPage } from './DiagnosticPage'
import { SubjectViewPage } from './SubjectViewPage'
import { SubjectsPage } from './SubjectsPage'

export function StudentShell() {
  const [subjectId, setSubjectId] = useState<string | null>(null)
  const [diagnosticTopic, setDiagnosticTopic] = useState<{ id: string; title: string } | null>(null)

  return (
    <RoleShell roleLabel="Student">
      {diagnosticTopic ? (
        <DiagnosticPage topicId={diagnosticTopic.id} topicTitle={diagnosticTopic.title} onBack={() => setDiagnosticTopic(null)} />
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

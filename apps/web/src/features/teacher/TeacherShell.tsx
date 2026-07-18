import { useState } from 'react'
import { RoleShell } from '../../components/RoleShell'
import { SubjectBuilderPage } from './SubjectBuilderPage'
import { SubjectsPage } from './SubjectsPage'

export function TeacherShell() {
  const [subjectId, setSubjectId] = useState<string | null>(null)

  return (
    <RoleShell roleLabel="Teacher" wide>
      {subjectId ? (
        <SubjectBuilderPage subjectId={subjectId} onBack={() => setSubjectId(null)} />
      ) : (
        <SubjectsPage onSelect={setSubjectId} />
      )}
    </RoleShell>
  )
}

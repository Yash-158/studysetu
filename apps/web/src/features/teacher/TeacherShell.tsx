import { useState } from 'react'
import { RoleShell } from '../../components/RoleShell'
import { BankReviewPage } from './BankReviewPage'
import { SubjectBuilderPage } from './SubjectBuilderPage'
import { SubjectsPage } from './SubjectsPage'

export function TeacherShell() {
  const [subjectId, setSubjectId] = useState<string | null>(null)
  const [reviewTopic, setReviewTopic] = useState<{ id: string; title: string } | null>(null)

  return (
    <RoleShell roleLabel="Teacher" wide>
      {reviewTopic ? (
        <BankReviewPage topicId={reviewTopic.id} topicTitle={reviewTopic.title} onBack={() => setReviewTopic(null)} />
      ) : subjectId ? (
        <SubjectBuilderPage
          subjectId={subjectId}
          onBack={() => setSubjectId(null)}
          onSelectTopic={(id, title) => setReviewTopic({ id, title })}
        />
      ) : (
        <SubjectsPage onSelect={setSubjectId} />
      )}
    </RoleShell>
  )
}

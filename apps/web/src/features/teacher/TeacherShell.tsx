import { useState } from 'react'
import { RoleShell } from '../../components/RoleShell'
import { AnalyticsShell } from '../analytics/AnalyticsShell'
import { BankReviewPage } from './BankReviewPage'
import { SubjectBuilderPage } from './SubjectBuilderPage'
import { SubjectsPage } from './SubjectsPage'

type Area = 'subjects' | 'analytics'

// M6-remediation Phase 2: ERP-style persistent left nav, replacing the old top ss-tabs switcher -
// same two areas (Subjects, Analytics; no other top-level teacher area exists yet), presentation
// only, zero change to what SubjectBuilderPage/AnalyticsShell actually do or call.
function TeacherSidebar({ area, onSelect }: { area: Area; onSelect: (area: Area) => void }) {
  const items: { key: Area; label: string }[] = [
    { key: 'subjects', label: 'Subjects' },
    { key: 'analytics', label: 'Analytics' },
  ]
  return (
    <div className="ss-sidebar-nav ss-no-print">
      {items.map((item) => (
        <button
          key={item.key}
          className={`ss-sidebar-link ${area === item.key ? 'ss-sidebar-link-active' : ''}`}
          onClick={() => onSelect(item.key)}
        >
          {item.label}
        </button>
      ))}
    </div>
  )
}

export function TeacherShell() {
  const [area, setArea] = useState<Area>('subjects')
  const [subjectId, setSubjectId] = useState<string | null>(null)
  const [reviewTopic, setReviewTopic] = useState<{ id: string; title: string } | null>(null)

  return (
    <RoleShell roleLabel="Teacher" sidebar={<TeacherSidebar area={area} onSelect={setArea} />}>
      {area === 'analytics' ? (
        <AnalyticsShell onReviewTopic={(id, title) => { setReviewTopic({ id, title }); setArea('subjects') }} />
      ) : reviewTopic ? (
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

import { useState } from 'react'
import { ExplorerPage } from './ExplorerPage'
import { StudentDetailPage } from './StudentDetailPage'
import { TodayPage } from './TodayPage'

type SubTab = 'today' | 'explorer'
type Viewing = { studentId: string; subjectId: string; misconceptionId?: string } | null

export function AnalyticsShell({ onReviewTopic }: { onReviewTopic: (topicId: string, topicTitle: string) => void }) {
  const [subTab, setSubTab] = useState<SubTab>('today')
  const [viewing, setViewing] = useState<Viewing>(null)

  if (viewing) {
    return (
      <StudentDetailPage
        studentId={viewing.studentId}
        subjectId={viewing.subjectId}
        misconceptionId={viewing.misconceptionId}
        onBack={() => setViewing(null)}
      />
    )
  }

  return (
    <div className="ss-stack">
      <div className="ss-tabs ss-no-print">
        <button className={`ss-tab ${subTab === 'today' ? 'ss-tab-active' : ''}`} onClick={() => setSubTab('today')}>Today</button>
        <button className={`ss-tab ${subTab === 'explorer' ? 'ss-tab-active' : ''}`} onClick={() => setSubTab('explorer')}>Explorer</button>
      </div>
      {subTab === 'today' ? (
        <TodayPage
          onViewStudent={(studentId, subjectId, misconceptionId) => setViewing({ studentId, subjectId, misconceptionId })}
          onReviewTopic={onReviewTopic}
        />
      ) : (
        <ExplorerPage onViewStudent={(studentId, subjectId) => setViewing({ studentId, subjectId })} />
      )}
    </div>
  )
}

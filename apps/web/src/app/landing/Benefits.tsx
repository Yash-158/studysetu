const ROWS = [
  { topic: 'Revision content', traditional: 'Same worksheet for every student', studysetu: "Personalized session built from each student's actual diagnostic gaps" },
  { topic: 'Question quality', traditional: 'Reused year over year; answers circulate', studysetu: 'Generated once per topic, teacher-reviewed before it reaches anyone' },
  { topic: 'Spotting misconceptions', traditional: 'Only visible if a teacher reads every answer sheet', studysetu: 'Every wrong option tagged with the specific misconception it represents' },
  { topic: 'Forgetting', traditional: 'Invisible until the next exam', studysetu: "Confidence decay resurfaces a topic automatically before it's forgotten" },
  { topic: 'Teacher time', traditional: 'Hours writing and marking practice questions', studysetu: 'One review-and-approve pass per topic, reused for the whole class' },
  { topic: 'AI trust', traditional: 'N/A', studysetu: 'Every AI answer stored and teacher-visible before a student sees it; AI never assigns a mark' },
]

export function Benefits() {
  return (
    <section id="about">
      <p className="landing-section-eyebrow">Why It's Different</p>
      <h2 className="landing-section-title">Traditional revision vs. StudySetu</h2>
      <div style={{ overflowX: 'auto' }}>
        <table className="landing-compare">
          <thead>
            <tr><th></th><th>Traditional revision</th><th>StudySetu</th></tr>
          </thead>
          <tbody>
            {ROWS.map((r) => (
              <tr key={r.topic}>
                <td><strong>{r.topic}</strong></td>
                <td className="landing-compare-no">{r.traditional}</td>
                <td className="landing-compare-yes">{r.studysetu}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}

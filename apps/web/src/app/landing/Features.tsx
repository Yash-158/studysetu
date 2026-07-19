const FEATURES = [
  {
    icon: '◎',
    title: 'Diagnostic Engine',
    body: "Every topic opens with a 5-question probe drawn from a teacher-reviewed item bank - stratified across easy/medium/hard, plus a slot pulled from a prerequisite topic when a student's history shows they're shaky there. No guessing at what to teach next.",
  },
  {
    icon: '↗',
    title: 'Mastery Tracking',
    body: 'A BKT-modeled mastery score per student per topic, updated from every answer they give. Confidence decays quietly with inactivity, so a topic a student has drifted from resurfaces on its own - revision that finds them, not the other way around.',
  },
  {
    icon: '▤',
    title: 'Teacher Analytics',
    body: "A timeline of every diagnostic, session, and mastery shift for every student - not a gradebook. Teachers see who's stuck and why, drill from class to topic to the exact wrong answers, and watch the effect of their own remediation.",
  },
]

export function Features() {
  return (
    <section id="features">
      <p className="landing-section-eyebrow">Features</p>
      <h2 className="landing-section-title">Built around one idea: teach the gap</h2>
      <p className="landing-section-lead">
        Not another content library. StudySetu figures out what a specific student needs, grounded in the teacher's own materials.
      </p>
      <div className="landing-card-grid">
        {FEATURES.map((f) => (
          <div className="landing-card" key={f.title}>
            <div className="landing-card-icon" aria-hidden="true">{f.icon}</div>
            <h3>{f.title}</h3>
            <p>{f.body}</p>
          </div>
        ))}
      </div>
    </section>
  )
}

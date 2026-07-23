import { StepFlow } from './StepFlow'

const FLOWS = [
  {
    role: 'Teacher',
    icon: '✎',
    steps: [
      'Build a subject as chapters of ordered topics and checkpoints',
      'Attach materials - PDFs, links, notes - that ground everything generated',
      'Generate a 12-15 item bank per topic, misconception-tagged',
      'Review the queue: approve-all, or edit item by item',
    ],
  },
  {
    role: 'Student',
    icon: '◈',
    steps: [
      'Open a topic and take the 5-question diagnostic',
      'Answer with neutral acknowledgment - no score pressure mid-probe',
      'See the full review: every question, the reasoning, what it revealed',
      'Get a personalized session, prerequisite revision injected first if needed',
    ],
  },
  {
    role: 'Institution admin',
    icon: '▦',
    steps: [
      'Import a roster by CSV - accounts and activation codes issued at once',
      'Group students into pools (a section, a batch, a cohort)',
      'Attach pools to subjects; new joiners never enroll silently',
      'See cohort-level analytics and the AI cost ledger, not raw logs',
    ],
  },
]

export function HowItWorks() {
  return (
    <section id="how-it-works">
      <div className="landing-container">
        <p className="landing-section-eyebrow">How It Works</p>
        <h2 className="landing-section-title">Three roles, one connected loop</h2>
        <p className="landing-section-lead">Nobody has to coordinate manually - the same data feeds every role's view.</p>
        <div className="landing-flow-grid">
          {FLOWS.map((f) => (
            <div className="landing-flow-card" key={f.role}>
              <div className="landing-card-icon" aria-hidden="true">{f.icon}</div>
              <h3>{f.role}</h3>
              <StepFlow steps={f.steps} />
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

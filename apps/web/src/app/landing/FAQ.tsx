const FAQS = [
  { q: 'Does the AI grade my students?', a: 'No. AI never assigns marks or mastery levels. Item generation and explanations are AI-written, but diagnosis and mastery tracking run on deterministic math (Bayesian Knowledge Tracing) - the same calculation every time, fully explainable.' },
  { q: 'What happens to the questions the AI generates?', a: "Every generated item bank lands in a teacher review queue first. Nothing reaches a student until a teacher approves it - approve-all in one click, or edit item by item. Draft items are never served, by design, not just by convention." },
  { q: 'Can I use my own teaching materials?', a: 'Yes. Upload PDFs, links, or typed notes at the subject, chapter, or topic level - item banks and explanations are grounded in what you actually attached, not a generic textbook.' },
  { q: 'Is this a chatbot?', a: "No. The diagnostic probe and the mastery graph are deterministic - nothing about what a student sees next is decided by an LLM improvising. AI writes content once; math decides what to show and when." },
  { q: 'What if a student shares their login?', a: "Every account is personal and institution-provisioned, not a shared PIN. Concurrent logins from two places raise a quiet flag to the teacher - sharing is possible but pointless, since it just pollutes your own history." },
]

export function FAQ() {
  return (
    <section id="faq">
      <p className="landing-section-eyebrow">FAQ</p>
      <h2 className="landing-section-title">Questions people actually ask</h2>
      <div>
        {FAQS.map((f) => (
          <details className="landing-faq-item" key={f.q}>
            <summary>{f.q}</summary>
            <p>{f.a}</p>
          </details>
        ))}
      </div>
    </section>
  )
}

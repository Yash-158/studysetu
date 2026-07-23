// Numbered, connected step visual (Phase 1 remediation) - replaces plain <ol> bullet text in
// HowItWorks so each role's journey reads as a flow, not a list. Stays a real <ol> under the
// hood (native list semantics for assistive tech); the numbered node is a decorative visual
// duplicate of the list's own ordinal, so it's aria-hidden.
export function StepFlow({ steps }: { steps: string[] }) {
  return (
    <ol className="landing-stepflow">
      {steps.map((step, i) => (
        <li className="landing-stepflow-step" key={step}>
          <span className="landing-stepflow-node" aria-hidden="true">{i + 1}</span>
          <span className="landing-stepflow-text">{step}</span>
        </li>
      ))}
    </ol>
  )
}

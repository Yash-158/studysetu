// DESIGN.md component inventory's linear progress case - a fixed-length sequence (the diagnostic
// probe) gets an at-a-glance visual alongside its own accessible "Question X of Y" text, which
// stays the source of truth for screen readers and existing e2e selectors.
export function ProgressBar({ current, total }: { current: number; total: number }) {
  return (
    <div className="ss-progress-bar" role="progressbar" aria-valuenow={current} aria-valuemin={1} aria-valuemax={total}>
      {Array.from({ length: total }, (_, i) => (
        <div key={i} className={`ss-progress-segment ${i < current ? 'ss-progress-segment-filled' : ''}`} />
      ))}
    </div>
  )
}

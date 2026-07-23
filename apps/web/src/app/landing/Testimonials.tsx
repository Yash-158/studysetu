// Placeholder testimonials (dummy data, per the design brief) - generic role-based attribution,
// not attributed to a specific real, verifiable person or institution.
const TESTIMONIALS = [
  { quote: "I used to write practice questions every single week. Now I review a bank once and it's done - for the whole class, every year after.", name: 'Faculty, Computer Science', kind: 'Teacher' },
  { quote: "The diagnostic told me I was actually shaky on Transforms, not Frequency Filtering like I thought. That's the part that clicked.", name: 'B.Tech, Semester 5', kind: 'Student' },
  { quote: 'Roster import and pools took an afternoon instead of a semester of spreadsheet chaos.', name: 'Academic Administrator', kind: 'Institution admin' },
]

export function Testimonials() {
  return (
    <section id="testimonials">
      <div className="landing-container">
        <p className="landing-section-eyebrow">What People Say</p>
        <h2 className="landing-section-title">Early feedback</h2>
        <div className="landing-testimonial-grid">
          {TESTIMONIALS.map((t) => (
            <div className="landing-testimonial" key={t.name}>
              <p className="landing-quote">&ldquo;{t.quote}&rdquo;</p>
              <p className="landing-attribution">{t.name} · {t.kind}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

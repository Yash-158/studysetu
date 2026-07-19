import { Link } from 'react-router-dom'
import { Button } from '../../components/Button'

export function Hero({ tagline, selfServeEnabled }: { tagline?: string; selfServeEnabled: boolean }) {
  return (
    <section id="top" className="landing-hero">
      <div>
        <h1>Every student, personally understood.</h1>
        <p>
          {tagline ?? 'StudySetu diagnoses what a student actually knows before teaching them anything - then builds a personalized session around exactly the gap it found, not the whole chapter again.'}
        </p>
        <div className="landing-hero-ctas">
          <Link to={selfServeEnabled ? '/teacher-signup' : '/activate'}><Button>Start free as a teacher</Button></Link>
          <a href="#how-it-works"><Button variant="ghost">See how it works</Button></a>
        </div>
        <p className="landing-hero-subnote">
          Given a roll number and activation code by your institution?{' '}
          <Link className="ss-link" to="/activate">Activate your account</Link>
        </p>
      </div>
      <div className="landing-illustration-placeholder" role="img" aria-label="Illustration placeholder: a student's diagnostic result flowing into a personalized revision session">
        [Illustration placeholder - a real illustration or product screenshot goes here]
      </div>
    </section>
  )
}

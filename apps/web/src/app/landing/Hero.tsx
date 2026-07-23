import { Link } from 'react-router-dom'
import { Button } from '../../components/Button'
import { HeroVideo } from './HeroVideo'

export function Hero({ tagline, selfServeEnabled }: { tagline?: string; selfServeEnabled: boolean }) {
  return (
    <section id="top" className="landing-hero">
      <div className="landing-container landing-hero-grid">
        <div className="landing-hero-copy">
          <h1>Every student, personally understood.</h1>
          <p className="landing-hero-lead">
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
        <div className="landing-hero-visual">
          <HeroVideo />
        </div>
      </div>
    </section>
  )
}

import { Link } from 'react-router-dom'
import { Button } from '../../components/Button'

export function Pricing({ selfServeEnabled }: { selfServeEnabled: boolean }) {
  return (
    <section id="pricing">
      <p className="landing-section-eyebrow">Pricing</p>
      <h2 className="landing-section-title">Start with one classroom, free</h2>
      <p className="landing-section-lead">Placeholder plans - final pricing to be confirmed.</p>
      <div className="landing-pricing-grid">
        <div className="landing-pricing-card">
          <h3>Solo Teacher</h3>
          <p className="landing-pricing-price">Free</p>
          <ul>
            <li>One personal classroom, no institution needed</li>
            <li>Full item-bank generation + diagnostic engine</li>
            <li>Mastery tracking for every enrolled student</li>
          </ul>
          <Link to={selfServeEnabled ? '/teacher-signup' : '/activate'}><Button>Start free</Button></Link>
        </div>
        <div className="landing-pricing-card landing-pricing-featured">
          <h3>Institution</h3>
          <p className="landing-pricing-price">Contact us</p>
          <ul>
            <li>Roster import, pools, and multi-teacher subjects</li>
            <li>Full analytics suite and AI cost dashboard</li>
            <li>Priced per student, per term - talk to us for a quote</li>
          </ul>
          <a href="#contact"><Button variant="ghost">Contact sales</Button></a>
        </div>
      </div>
    </section>
  )
}

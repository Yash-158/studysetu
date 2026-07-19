import { Link } from 'react-router-dom'
import { Button } from '../../components/Button'
import { Logo } from '../../components/Logo'

export function Navbar({ selfServeEnabled }: { selfServeEnabled: boolean }) {
  return (
    <header className="landing-navbar">
      <a href="#top" aria-label="StudySetu home"><Logo /></a>
      <nav className="landing-navbar-links landing-navbar-mobile-hide">
        <a href="#top">Home</a>
        <a href="#features">Features</a>
        <a href="#how-it-works">How It Works</a>
        <a href="#pricing">Pricing</a>
        <a href="#about">About</a>
        <a href="#contact">Contact</a>
      </nav>
      <div className="landing-navbar-cta">
        <Link to="/login"><Button variant="ghost">Log in</Button></Link>
        <Link to={selfServeEnabled ? '/teacher-signup' : '/activate'}><Button>Get Started</Button></Link>
      </div>
    </header>
  )
}

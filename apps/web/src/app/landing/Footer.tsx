import { Logo } from '../../components/Logo'

export function Footer({ orgName }: { orgName?: string }) {
  return (
    <footer className="landing-footer" id="contact">
      <div className="landing-footer-grid">
        <div>
          <Logo size="lg" />
          <p className="landing-footer-blurb">
            An AI revision and assessment companion built around one idea: diagnose the real gap, then teach that.
          </p>
        </div>
        <div>
          <h4>Product</h4>
          <a href="#features">Features</a>
          <a href="#how-it-works">How It Works</a>
          <a href="#pricing">Pricing</a>
        </div>
        <div>
          <h4>Company</h4>
          <a href="#about">About</a>
          <a href="#testimonials">Testimonials</a>
          <a href="#faq">FAQ</a>
        </div>
        <div>
          <h4>Contact</h4>
          <a href="mailto:hello@studysetu.example">hello@studysetu.example</a>
        </div>
      </div>
      <div className="landing-footer-bottom">© {new Date().getFullYear()} {orgName ?? 'StudySetu'}. All rights reserved.</div>
    </footer>
  )
}

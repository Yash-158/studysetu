import { Navbar } from './landing/Navbar'
import { Hero } from './landing/Hero'
import { Features } from './landing/Features'
import { HowItWorks } from './landing/HowItWorks'
import { Benefits } from './landing/Benefits'
import { Testimonials } from './landing/Testimonials'
import { Pricing } from './landing/Pricing'
import { FAQ } from './landing/FAQ'
import { Footer } from './landing/Footer'
import './landing/landing.css'
import { getConfig } from '../lib/config'

export function LandingPage() {
  const config = getConfig()
  const product = config.product as { name?: string; tagline?: string; org?: string } | undefined
  const selfServeEnabled = Boolean((config.features as Record<string, unknown> | undefined)?.self_serve_teacher_tier)

  return (
    <div className="landing">
      <Navbar selfServeEnabled={selfServeEnabled} />
      <Hero tagline={product?.tagline} selfServeEnabled={selfServeEnabled} />
      <Features />
      <HowItWorks />
      <Benefits />
      <Testimonials />
      <Pricing selfServeEnabled={selfServeEnabled} />
      <FAQ />
      <Footer orgName={product?.org ?? product?.name} />
    </div>
  )
}

// DESIGN.md component inventory: Button (build once, reuse everywhere). Plain CSS + CSS vars
// (no Tailwind build wiring exists yet - see styles/index.css); colors never hardcoded.
import type { ButtonHTMLAttributes } from 'react'

type Variant = 'primary' | 'ghost'

export function Button({
  variant = 'primary',
  className = '',
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant }) {
  return <button className={`ss-button ss-button-${variant} ${className}`.trim()} {...rest} />
}

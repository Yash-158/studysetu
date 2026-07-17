// DESIGN.md component inventory: Card (build once, reuse everywhere).
import type { HTMLAttributes } from 'react'

export function Card({ className = '', ...rest }: HTMLAttributes<HTMLDivElement>) {
  return <div className={`ss-card ${className}`.trim()} {...rest} />
}

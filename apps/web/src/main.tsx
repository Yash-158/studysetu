// StudySetu entrypoint. Infrastructure only: config bootstrap + router shell. TODO(M1): routes per role.
import React from 'react'
import { createRoot } from 'react-dom/client'
import { loadConfig } from './lib/config'

loadConfig().then((cfg) => {
  createRoot(document.getElementById('root')!).render(
    <React.StrictMode>
      <main style={{ fontFamily: 'system-ui', padding: 24 }}>
        <h1>{cfg.product?.name ?? 'StudySetu'}</h1>
        <p>{cfg.product?.tagline}</p>
        <p>Foundation shell. Milestones begin at docs/PROMPTS.md M1.</p>
      </main>
    </React.StrictMode>,
  )
})

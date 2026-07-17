// StudySetu entrypoint. Infrastructure only: config bootstrap + router shell mount.
import React from 'react'
import { createRoot } from 'react-dom/client'
import { loadConfig } from './lib/config'
import { App } from './app/App'
import './styles/index.css'

loadConfig().then(() => {
  createRoot(document.getElementById('root')!).render(
    <React.StrictMode>
      <App />
    </React.StrictMode>,
  )
})

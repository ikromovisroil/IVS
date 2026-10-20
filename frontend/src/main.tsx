import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './ds'
import './index.css'
import App from './App.tsx'
import { BASENAME } from './routes'
import { applyTheme, storedTheme } from './theme'

// Mavzu birinchi chizishdan oldin — tungi rejimda oq "chaqnash" bo'lmasin
applyTheme(storedTheme())

// Dev serverda http://localhost:5173/ ochilsa — /app/ ga (productionda bu yo'lni Django beradi)
if (!window.location.pathname.startsWith(BASENAME)) window.location.replace(BASENAME + '/')

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)

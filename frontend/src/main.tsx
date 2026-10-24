import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'
import { ConversationProvider } from '@elevenlabs/react'
import './index.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode><ConversationProvider><App /></ConversationProvider></StrictMode>,
)

import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App/App.tsx'
import { ThemeProvider } from './components/theme-provide.tsx'

createRoot(document.getElementById('root')!).render(
  <ThemeProvider defaultTheme="dark">
			<App />
		</ThemeProvider>
)

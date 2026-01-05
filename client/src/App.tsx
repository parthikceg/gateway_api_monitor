import { useState } from 'react'
import { Layout } from '@/components/Layout'
import { Dashboard } from '@/pages/Dashboard'
import { Changes } from '@/pages/Changes'
import { Explorer } from '@/pages/Explorer'
import { Snapshots } from '@/pages/Snapshots'
import { Compare } from '@/pages/Compare'
import { ChatWidget } from '@/components/ChatWidget'

interface NavigationParams {
  tier?: string
  severity?: string
}

function App() {
  const [currentPage, setCurrentPage] = useState('dashboard')
  const [navParams, setNavParams] = useState<NavigationParams>({})

  const handleNavigate = (page: string, params?: Record<string, string>) => {
    setCurrentPage(page)
    setNavParams(params || {})
  }

  const renderPage = () => {
    switch (currentPage) {
      case 'dashboard':
        return <Dashboard onNavigate={handleNavigate} />
      case 'changes':
        return <Changes initialSeverity={navParams.severity} initialTier={navParams.tier} />
      case 'explorer':
        return <Explorer initialTier={navParams.tier} />
      case 'snapshots':
        return <Snapshots />
      case 'compare':
        return <Compare />
      default:
        return <Dashboard onNavigate={handleNavigate} />
    }
  }

  return (
    <>
      <Layout currentPage={currentPage} onNavigate={handleNavigate}>
        {renderPage()}
      </Layout>
      {currentPage !== 'explorer' && <ChatWidget />}
    </>
  )
}

export default App

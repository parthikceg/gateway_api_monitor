import { useState } from 'react'
import { Layout } from '@/components/Layout'
import { Dashboard } from '@/pages/Dashboard'
import { Changes } from '@/pages/Changes'
import { Explorer } from '@/pages/Explorer'
import { Snapshots } from '@/pages/Snapshots'
import { Compare } from '@/pages/Compare'

function App() {
  const [currentPage, setCurrentPage] = useState('dashboard')

  const renderPage = () => {
    switch (currentPage) {
      case 'dashboard':
        return <Dashboard />
      case 'changes':
        return <Changes />
      case 'explorer':
        return <Explorer />
      case 'snapshots':
        return <Snapshots />
      case 'compare':
        return <Compare />
      default:
        return <Dashboard />
    }
  }

  return (
    <Layout currentPage={currentPage} onNavigate={setCurrentPage}>
      {renderPage()}
    </Layout>
  )
}

export default App

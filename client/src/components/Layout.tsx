import { useState } from 'react'
import { 
  Activity, 
  Database, 
  GitCompare, 
  LayoutDashboard, 
  Menu,
  X,
  Zap
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Separator } from '@/components/ui/separator'

interface LayoutProps {
  children: React.ReactNode
  currentPage: string
  onNavigate: (page: string) => void
}

const navItems = [
  { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { id: 'changes', label: 'Changes', icon: Activity },
  { id: 'explorer', label: 'Object Explorer', icon: Database },
  { id: 'snapshots', label: 'Snapshots', icon: Zap },
  { id: 'compare', label: 'Compare', icon: GitCompare },
]

export function Layout({ children, currentPage, onNavigate }: LayoutProps) {
  const [sidebarOpen, setSidebarOpen] = useState(true)

  return (
    <div className="flex h-screen overflow-hidden">
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-50 flex w-64 flex-col border-r bg-card transition-transform duration-300 lg:static lg:translate-x-0",
          sidebarOpen ? "translate-x-0" : "-translate-x-full"
        )}
      >
        <div className="flex h-16 items-center gap-2 border-b px-6">
          <Activity className="h-6 w-6 text-primary" />
          <span className="font-semibold text-lg">Gateway Monitor</span>
        </div>
        
        <ScrollArea className="flex-1 py-4">
          <nav className="space-y-1 px-3">
            {navItems.map((item) => {
              const Icon = item.icon
              return (
                <button
                  key={item.id}
                  onClick={() => onNavigate(item.id)}
                  className={cn(
                    "flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                    currentPage === item.id
                      ? "bg-primary text-primary-foreground"
                      : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
                  )}
                >
                  <Icon className="h-4 w-4" />
                  {item.label}
                </button>
              )
            })}
          </nav>
          
          <Separator className="my-4" />
          
          <div className="px-6">
            <h4 className="mb-2 text-xs font-semibold uppercase text-muted-foreground">
              Gateways
            </h4>
            <div className="space-y-1">
              <div className="flex items-center gap-2 rounded-lg bg-accent/50 px-3 py-2 text-sm">
                <div className="h-2 w-2 rounded-full bg-green-500" />
                Stripe
              </div>
              <div className="flex items-center gap-2 rounded-lg px-3 py-2 text-sm text-muted-foreground">
                <div className="h-2 w-2 rounded-full bg-gray-300" />
                Braintree (Soon)
              </div>
            </div>
          </div>
        </ScrollArea>
        
        <div className="border-t p-4">
          <p className="text-xs text-muted-foreground">
            Gateway Monitor v2.0.0
          </p>
        </div>
      </aside>

      <div className="flex flex-1 flex-col overflow-hidden">
        <header className="flex h-16 items-center gap-4 border-b bg-card px-6">
          <Button
            variant="ghost"
            size="icon"
            className="lg:hidden"
            onClick={() => setSidebarOpen(!sidebarOpen)}
          >
            {sidebarOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </Button>
          
          <h1 className="text-xl font-semibold capitalize">
            {navItems.find(item => item.id === currentPage)?.label || 'Dashboard'}
          </h1>
        </header>

        <main className="flex-1 overflow-auto bg-background p-6">
          {children}
        </main>
      </div>

      {sidebarOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/50 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}
    </div>
  )
}

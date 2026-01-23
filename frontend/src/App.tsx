import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Toaster } from './components/ui/sonner';
import { ErrorBoundary } from './components/ErrorBoundary';
import { EnvironmentProvider } from './contexts/EnvironmentContext';
import { AccountProvider } from './contexts/AccountContext';
import { SystemStatusBar } from './components/SystemStatusBar';
import { MobileBottomTabs } from './components/layouts/MobileBottomTabs';
import { DesktopSidebar } from './components/layouts/DesktopSidebar';
import { PageBackground } from './components/layouts/PageBackground';
import { StockAnalysis } from './pages/StockAnalysis/StockAnalysis';
import { Live20Dashboard } from './components/live20/Live20Dashboard';
import { Live20RunDetail } from './pages/Live20RunDetail';
import { StockLists } from './pages/StockLists';
import { Arena } from './pages/Arena';
import { ArenaSimulationDetail } from './pages/ArenaSimulationDetail';
import './index.css';

function App() {
  return (
    <BrowserRouter>
      <ErrorBoundary>
        <EnvironmentProvider>
          <AccountProvider>
            <div className="dark overflow-x-hidden">
              {/* Subtle grid background pattern */}
              <PageBackground />

              {/* Flex container: sidebar + main content */}
              <div className="flex min-h-screen relative z-[1]">
                {/* Desktop Sidebar (hidden on mobile) */}
                <DesktopSidebar />

                {/* Main Content Area */}
                <main className="flex-1 pb-20 md:pb-0">
                  {/* System status bar at top of content area - stays fixed on mobile */}
                  <div className="sticky top-0 z-40">
                    <SystemStatusBar />
                  </div>

                  <Routes>
                    <Route path="/" element={<StockAnalysis />} />
                    <Route path="/stock/:symbol" element={<StockAnalysis />} />
                    <Route path="/live-20" element={<Live20Dashboard />} />
                    <Route path="/live-20/runs/:id" element={<Live20RunDetail />} />
                    <Route path="/lists" element={<StockLists />} />
                    <Route path="/arena" element={<Arena />} />
                    <Route path="/arena/:id" element={<ArenaSimulationDetail />} />
                  </Routes>
                </main>
              </div>

              {/* Mobile Bottom Tabs (hidden on desktop) */}
              <MobileBottomTabs />

              <Toaster />
            </div>
          </AccountProvider>
        </EnvironmentProvider>
      </ErrorBoundary>
    </BrowserRouter>
  );
}

export default App;

import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Toaster } from './components/ui/sonner';
import { ErrorBoundary } from './components/ErrorBoundary';
import { EnvironmentProvider } from './contexts/EnvironmentContext';
import { MobileBottomTabs } from './components/layouts/MobileBottomTabs';
import { DesktopSidebar } from './components/layouts/DesktopSidebar';
import { PageBackground } from './components/layouts/PageBackground';
import './index.css';

function App() {
  return (
    <BrowserRouter>
      <ErrorBoundary>
        <EnvironmentProvider>
          <div className="dark overflow-x-hidden">
            {/* Subtle grid background pattern */}
            <PageBackground />

            {/* Flex container: sidebar + main content */}
            <div className="flex min-h-screen relative z-[1]">
              {/* Desktop Sidebar (hidden on mobile) */}
              <DesktopSidebar />

              {/* Main Content Area */}
              <main className="flex-1 pb-20 md:pb-0">
                <Routes>
                  <Route path="/" element={<div />} />
                </Routes>
              </main>
            </div>

            {/* Mobile Bottom Tabs (hidden on desktop) */}
            <MobileBottomTabs />

            <Toaster />
          </div>
        </EnvironmentProvider>
      </ErrorBoundary>
    </BrowserRouter>
  );
}

export default App;

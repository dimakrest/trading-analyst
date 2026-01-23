/**
 * Arena Page
 *
 * Main page for the Trading Agent Arena feature.
 * Provides tabs for creating new simulations and viewing history.
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { AlertCircle } from 'lucide-react';
import { toast } from 'sonner';
import { Alert, AlertDescription } from '../components/ui/alert';
import { Button } from '../components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { ArenaSetupForm } from '../components/arena/ArenaSetupForm';
import { ArenaSimulationList } from '../components/arena/ArenaSimulationList';
import { useActiveArenaSimulation } from '../hooks/useActiveArenaSimulation';
import { createSimulation, listSimulations } from '../services/arenaService';
import type { CreateSimulationRequest, Simulation } from '../types/arena';

/** Type for navigation state when replaying */
interface ReplayState {
  replaySimulation?: Simulation;
}

/**
 * Arena Page Component
 *
 * Features:
 * - Header with title "Arena" and subtitle "Trading Agent Simulator"
 * - Active simulation banner with "View Progress" button
 * - Tabs: "New Simulation" and "History"
 * - New Simulation tab shows ArenaSetupForm
 * - History tab shows ArenaSimulationList
 */
export const Arena = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const replayState = location.state as ReplayState | null;
  const replaySimulation = replayState?.replaySimulation;

  const [isCreating, setIsCreating] = useState(false);
  const [simulations, setSimulations] = useState<Simulation[]>([]);
  const [isLoadingList, setIsLoadingList] = useState(true);
  const [activeTab, setActiveTab] = useState<string>('new');

  // Check for active (running/pending) simulation on mount
  const { activeSimulation, clearActiveSimulation } = useActiveArenaSimulation();

  // Fetch simulations list
  const fetchSimulations = useCallback(async () => {
    try {
      setIsLoadingList(true);
      const response = await listSimulations();
      setSimulations(response.items);
    } catch {
      toast.error('Failed to load simulations');
    } finally {
      setIsLoadingList(false);
    }
  }, []);

  // Load simulations on mount
  useEffect(() => {
    fetchSimulations();
  }, [fetchSimulations]);

  // Handle replay: switch to "new" tab and clear navigation state
  useEffect(() => {
    if (replaySimulation) {
      setActiveTab('new');
      // Clear state to prevent re-triggering on browser back/forward
      window.history.replaceState({}, document.title);
    }
  }, [replaySimulation]);

  // Convert Simulation to form initialValues (memoized to prevent unnecessary re-renders)
  const initialValues = useMemo(() => {
    if (!replaySimulation) return undefined;
    return {
      symbols: replaySimulation.symbols,
      start_date: replaySimulation.start_date,
      end_date: replaySimulation.end_date,
      initial_capital: parseFloat(replaySimulation.initial_capital),
      position_size: parseFloat(replaySimulation.position_size),
      trailing_stop_pct: replaySimulation.trailing_stop_pct
        ? parseFloat(replaySimulation.trailing_stop_pct)
        : 5,
      min_buy_score: replaySimulation.min_buy_score ?? 60,
      stock_list_id: replaySimulation.stock_list_id,
      stock_list_name: replaySimulation.stock_list_name,
    };
  }, [replaySimulation]);

  // Handle creating a new simulation
  const handleCreate = async (request: CreateSimulationRequest) => {
    try {
      setIsCreating(true);
      const simulation = await createSimulation(request);
      toast.success('Simulation started - processing in background');
      navigate(`/arena/${simulation.id}`);
    } catch {
      toast.error('Failed to create simulation');
    } finally {
      setIsCreating(false);
    }
  };

  // Handle resuming active simulation
  const handleResumeActive = () => {
    if (activeSimulation) {
      clearActiveSimulation();
      navigate(`/arena/${activeSimulation.id}`);
    }
  };

  // Handle replay simulation
  const handleReplay = (simulation: Simulation) => {
    navigate('/arena', { state: { replaySimulation: simulation } });
  };

  return (
    <div className="container mx-auto px-6 py-6 md:py-8">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold">Arena</h1>
        <p className="text-muted-foreground">Trading Agent Simulator</p>
      </div>

      {/* Active Simulation Banner */}
      {activeSimulation && (
        <Alert className="mb-6">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription className="flex items-center justify-between">
            <span>
              Simulation #{activeSimulation.id} is {activeSimulation.status} (
              {activeSimulation.current_day}/{activeSimulation.total_days || '?'} days)
            </span>
            <Button size="sm" onClick={handleResumeActive}>
              View Progress
            </Button>
          </AlertDescription>
        </Alert>
      )}

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
        <TabsList className="mb-6">
          <TabsTrigger value="new">New Simulation</TabsTrigger>
          <TabsTrigger value="history">History</TabsTrigger>
        </TabsList>

        {/* New Simulation Tab */}
        <TabsContent value="new">
          <div className="max-w-2xl">
            <ArenaSetupForm
              onSubmit={handleCreate}
              isLoading={isCreating}
              initialValues={initialValues}
            />
          </div>
        </TabsContent>

        {/* History Tab */}
        <TabsContent value="history">
          <ArenaSimulationList
            simulations={simulations}
            isLoading={isLoadingList}
            onRefresh={fetchSimulations}
            onReplay={handleReplay}
          />
        </TabsContent>
      </Tabs>
    </div>
  );
};

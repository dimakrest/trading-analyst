/**
 * Setup Simulation Page
 *
 * Allows users to define multiple trading setups, run a historical simulation,
 * and view the resulting P&L metrics and per-trade breakdown.
 *
 * The simulation is synchronous: the page POSTs setup definitions and receives
 * complete results in a single response (no polling or background workers).
 */
import { useState } from 'react';
import { toast } from 'sonner';
import { SetupSimForm } from '../components/setup-sim/SetupSimForm';
import { SetupSimResults } from '../components/setup-sim/SetupSimResults';
import { runSetupSimulation } from '../services/setupSimService';
import { extractErrorMessage } from '../utils/errors';
import type { RunSetupSimulationRequest, SetupSimulationResponse } from '../types/setupSim';

/**
 * Setup Simulation Page Component
 *
 * Features:
 * - Header with title and subtitle
 * - SetupSimForm for defining setups and end date
 * - SetupSimResults displayed below the form after a successful run
 * - Toast notifications for success and error states
 */
export const SetupSimulation = () => {
  const [isLoading, setIsLoading] = useState(false);
  const [results, setResults] = useState<SetupSimulationResponse | null>(null);

  const handleRun = async (request: RunSetupSimulationRequest) => {
    try {
      setIsLoading(true);
      setResults(null);
      const response = await runSetupSimulation(request);
      setResults(response);
      toast.success(`Simulation complete \u2014 ${response.summary.total_trades} trades`);
    } catch (err) {
      toast.error(extractErrorMessage(err, 'Failed to run simulation'));
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="container mx-auto px-6 py-6 md:py-8">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold">Setup Simulation</h1>
        <p className="text-muted-foreground">Backtest user-defined trading setups against historical price data</p>
      </div>

      {/* Form */}
      <div className="max-w-3xl">
        <SetupSimForm onSubmit={handleRun} isLoading={isLoading} />
      </div>

      {/* Results (shown after successful simulation) */}
      {results && (
        <div className="mt-8 max-w-5xl">
          <SetupSimResults results={results} />
        </div>
      )}
    </div>
  );
};

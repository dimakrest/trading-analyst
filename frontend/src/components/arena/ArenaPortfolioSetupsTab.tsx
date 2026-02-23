import { useEffect, useState } from 'react';
import { Loader2, Pencil, Plus, Trash2 } from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '../ui/button';
import { Card, CardContent } from '../ui/card';
import { Badge } from '../ui/badge';
import {
  CreatePortfolioDialog,
  DeletePortfolioDialog,
  EditPortfolioDialog,
} from '../portfolioConfigs';
import { portfolioConfigService } from '../../services/portfolioConfigService';
import type {
  CreatePortfolioConfigRequest,
  PortfolioConfig,
  UpdatePortfolioConfigRequest,
} from '../../types/portfolioConfig';
import { PORTFOLIO_STRATEGIES } from '../../constants/portfolio';
import { extractErrorMessage } from '../../utils/errors';

const describeStrategy = (strategy: string): string => {
  return PORTFOLIO_STRATEGIES.find((option) => option.name === strategy)?.label ?? strategy;
};

/**
 * Portfolio setup management tab for Arena.
 */
export const ArenaPortfolioSetupsTab = () => {
  const [configs, setConfigs] = useState<PortfolioConfig[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [editingConfig, setEditingConfig] = useState<PortfolioConfig | null>(null);
  const [deletingConfig, setDeletingConfig] = useState<PortfolioConfig | null>(null);

  const [isCreating, setIsCreating] = useState(false);
  const [isUpdating, setIsUpdating] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  const loadConfigs = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await portfolioConfigService.getConfigs();
      setConfigs(response.items);
    } catch (err) {
      setError(extractErrorMessage(err));
      toast.error('Failed to load portfolio setups');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadConfigs();
  }, []);

  const handleCreate = async (data: CreatePortfolioConfigRequest): Promise<PortfolioConfig> => {
    setIsCreating(true);
    try {
      const config = await portfolioConfigService.createConfig(data);
      setConfigs((prev) => [...prev, config]);
      toast.success(`Portfolio setup "${config.name}" created`);
      return config;
    } catch (err) {
      toast.error(extractErrorMessage(err));
      throw err;
    } finally {
      setIsCreating(false);
    }
  };

  const handleUpdate = async (
    id: number,
    data: UpdatePortfolioConfigRequest
  ): Promise<PortfolioConfig> => {
    setIsUpdating(true);
    try {
      const config = await portfolioConfigService.updateConfig(id, data);
      setConfigs((prev) => prev.map((item) => (item.id === id ? config : item)));
      toast.success(`Portfolio setup "${config.name}" updated`);
      return config;
    } catch (err) {
      toast.error(extractErrorMessage(err));
      throw err;
    } finally {
      setIsUpdating(false);
    }
  };

  const handleDelete = async (config: PortfolioConfig) => {
    setIsDeleting(true);
    try {
      await portfolioConfigService.deleteConfig(config.id);
      setConfigs((prev) => prev.filter((item) => item.id !== config.id));
      toast.success(`Portfolio setup "${config.name}" deleted`);
    } catch (err) {
      toast.error(extractErrorMessage(err));
      throw err;
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <div className="space-y-5 max-w-3xl">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h3 className="text-base font-semibold text-text-primary">Portfolio Setups</h3>
          <p className="text-sm text-text-muted">
            Create reusable portfolio constraints and select them in New Simulation
          </p>
        </div>
        <Button onClick={() => setCreateDialogOpen(true)} disabled={isLoading}>
          <Plus className="w-4 h-4 mr-2" />
          New Setup
        </Button>
      </div>

      {isLoading && (
        <div className="flex items-center justify-center py-10">
          <Loader2 className="h-7 w-7 animate-spin text-text-muted" />
        </div>
      )}

      {error && !isLoading && (
        <Card className="border-accent-bearish bg-accent-bearish-muted">
          <CardContent className="p-5">
            <p className="text-sm text-text-primary">{error}</p>
            <Button onClick={loadConfigs} variant="outline" className="mt-3">
              Retry
            </Button>
          </CardContent>
        </Card>
      )}

      {!isLoading && !error && configs.length === 0 && (
        <Card className="border-default">
          <CardContent className="p-8 text-center">
            <p className="text-text-muted">No portfolio setups yet.</p>
            <Button onClick={() => setCreateDialogOpen(true)} className="mt-4">
              Create First Setup
            </Button>
          </CardContent>
        </Card>
      )}

      {!isLoading && !error && configs.length > 0 && (
        <div className="grid gap-3">
          {configs.map((config) => (
            <Card key={config.id} className="border-default hover:border-accent-primary transition-colors">
              <CardContent className="p-4">
                <div className="flex items-center justify-between gap-4">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <h4 className="font-semibold text-text-primary truncate">{config.name}</h4>
                      <Badge variant="outline" className="text-[10px]">
                        {describeStrategy(config.portfolio_strategy)}
                      </Badge>
                    </div>
                    <p className="text-xs text-text-muted mt-1 font-mono">
                      Size: ${config.position_size} | Min score: {config.min_buy_score} |{' '}
                      Stop: {config.trailing_stop_pct}% |{' '}
                      Max/sector: {config.max_per_sector ?? 'unlimited'} | Max open:{' '}
                      {config.max_open_positions ?? 'unlimited'}
                    </p>
                  </div>

                  <div className="flex items-center gap-2">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setEditingConfig(config)}
                      className="h-9 w-9 p-0"
                      aria-label="Edit setup"
                    >
                      <Pencil className="h-4 w-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setDeletingConfig(config)}
                      className="h-9 w-9 p-0 hover:text-accent-bearish"
                      aria-label="Delete setup"
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <CreatePortfolioDialog
        open={createDialogOpen}
        onOpenChange={setCreateDialogOpen}
        onSubmit={handleCreate}
        isSubmitting={isCreating}
      />

      <EditPortfolioDialog
        config={editingConfig}
        open={editingConfig !== null}
        onOpenChange={(open) => !open && setEditingConfig(null)}
        onSubmit={handleUpdate}
        isSubmitting={isUpdating}
      />

      <DeletePortfolioDialog
        config={deletingConfig}
        open={deletingConfig !== null}
        onOpenChange={(open) => !open && setDeletingConfig(null)}
        onConfirm={handleDelete}
        isDeleting={isDeleting}
      />
    </div>
  );
};

import { useState, useEffect } from 'react';
import { Plus, Pencil, Trash2, Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '../components/ui/button';
import { Card, CardContent } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import {
  CreateAgentDialog,
  EditAgentDialog,
  DeleteAgentDialog,
} from '../components/agents';
import { agentConfigService } from '../services/agentConfigService';
import type { AgentConfig, CreateAgentConfigRequest, UpdateAgentConfigRequest } from '../types/agentConfig';
import { extractErrorMessage } from '../utils/errors';

/**
 * Agents management page
 *
 * Features:
 * - View all agent configurations as cards
 * - Create new agents with name and algorithm
 * - Edit existing agents (rename, change algorithm)
 * - Delete agents with confirmation
 * - Empty state when only default exists
 * - Loading state while fetching
 */
export const Agents = () => {
  const [configs, setConfigs] = useState<AgentConfig[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Dialog states
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [editingConfig, setEditingConfig] = useState<AgentConfig | null>(null);
  const [deletingConfig, setDeletingConfig] = useState<AgentConfig | null>(null);

  // Submission states
  const [isCreating, setIsCreating] = useState(false);
  const [isUpdating, setIsUpdating] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  // Load configs on mount
  useEffect(() => {
    loadConfigs();
  }, []);

  const loadConfigs = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await agentConfigService.getConfigs();
      setConfigs(response.items);
    } catch (err) {
      setError(extractErrorMessage(err));
      toast.error('Failed to load agent configurations');
    } finally {
      setIsLoading(false);
    }
  };

  // Handlers
  const handleCreateConfig = async (data: CreateAgentConfigRequest): Promise<AgentConfig> => {
    setIsCreating(true);
    try {
      const newConfig = await agentConfigService.createConfig(data);
      toast.success(`Agent "${data.name}" created successfully`);
      setConfigs((prev) => [...prev, newConfig]);
      return newConfig;
    } catch (err) {
      toast.error(extractErrorMessage(err));
      throw err; // Re-throw to keep dialog open
    } finally {
      setIsCreating(false);
    }
  };

  const handleUpdateConfig = async (id: number, data: UpdateAgentConfigRequest): Promise<AgentConfig> => {
    setIsUpdating(true);
    try {
      const updatedConfig = await agentConfigService.updateConfig(id, data);
      toast.success(`Agent "${updatedConfig.name}" updated`);
      setConfigs((prev) => prev.map((c) => (c.id === id ? updatedConfig : c)));
      return updatedConfig;
    } catch (err) {
      toast.error(extractErrorMessage(err));
      throw err; // Re-throw to keep dialog open
    } finally {
      setIsUpdating(false);
    }
  };

  const handleDeleteConfig = async (config: AgentConfig) => {
    setIsDeleting(true);
    try {
      await agentConfigService.deleteConfig(config.id);
      toast.success(`Agent "${config.name}" deleted`);
      setConfigs((prev) => prev.filter((c) => c.id !== config.id));
    } catch (err) {
      toast.error(extractErrorMessage(err));
      throw err; // Re-throw to keep dialog open
    } finally {
      setIsDeleting(false);
    }
  };

  const handleEditClick = (config: AgentConfig) => {
    setEditingConfig(config);
  };

  const handleDeleteClick = (config: AgentConfig) => {
    setDeletingConfig(config);
  };

  return (
    <div className="flex-1 p-6 flex flex-col gap-5 max-w-[1200px] mx-auto w-full">
      {/* Page Header */}
      <div className="flex items-center justify-between gap-6">
        <div>
          <h1 className="font-display text-2xl font-bold tracking-tight text-text-primary">
            Agents
          </h1>
          <p className="text-sm text-text-muted mt-1">
            Manage scoring algorithm configurations for Live20 and Arena
          </p>
        </div>
        <Button
          onClick={() => setCreateDialogOpen(true)}
          className="flex items-center gap-2"
          disabled={isLoading}
        >
          <Plus className="w-[18px] h-[18px]" />
          New Agent
        </Button>
      </div>

      {/* Loading State */}
      {isLoading && (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="w-8 h-8 animate-spin text-text-muted" />
        </div>
      )}

      {/* Error State */}
      {error && !isLoading && (
        <Card className="border-accent-bearish bg-accent-bearish-muted">
          <CardContent className="p-6">
            <p className="text-sm text-text-primary">{error}</p>
            <Button onClick={loadConfigs} variant="outline" className="mt-4">
              Retry
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Agent Configs List */}
      {!isLoading && !error && configs.length === 0 && (
        <Card className="border-default">
          <CardContent className="p-8 text-center">
            <p className="text-text-muted">No agent configurations found.</p>
            <Button onClick={() => setCreateDialogOpen(true)} className="mt-4">
              Create Your First Agent
            </Button>
          </CardContent>
        </Card>
      )}

      {!isLoading && !error && configs.length > 0 && (
        <div className="grid gap-4">
          {configs.map((config) => (
            <Card key={config.id} className="border-default hover:border-accent-primary transition-colors">
              <CardContent className="p-5">
                <div className="flex items-center justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-3">
                      <h3 className="font-semibold text-base text-text-primary truncate">
                        {config.name}
                      </h3>
                      <Badge
                        variant="outline"
                        className="text-[10px] font-mono px-2 py-0.5 uppercase"
                      >
                        {config.scoring_algorithm}
                      </Badge>
                    </div>
                    <p className="text-xs text-text-muted mt-1">
                      Agent type: {config.agent_type}
                    </p>
                  </div>

                  {/* Actions */}
                  <div className="flex items-center gap-2">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleEditClick(config)}
                      className="h-9 w-9 p-0"
                      aria-label="Edit agent"
                    >
                      <Pencil className="h-4 w-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleDeleteClick(config)}
                      className="h-9 w-9 p-0 hover:text-accent-bearish"
                      aria-label="Delete agent"
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

      {/* Create Dialog */}
      <CreateAgentDialog
        open={createDialogOpen}
        onOpenChange={setCreateDialogOpen}
        onSubmit={handleCreateConfig}
        isSubmitting={isCreating}
      />

      {/* Edit Dialog */}
      <EditAgentDialog
        config={editingConfig}
        open={editingConfig !== null}
        onOpenChange={(open) => !open && setEditingConfig(null)}
        onSubmit={handleUpdateConfig}
        isSubmitting={isUpdating}
      />

      {/* Delete Dialog */}
      <DeleteAgentDialog
        config={deletingConfig}
        open={deletingConfig !== null}
        onOpenChange={(open) => !open && setDeletingConfig(null)}
        onConfirm={handleDeleteConfig}
        isDeleting={isDeleting}
      />
    </div>
  );
};

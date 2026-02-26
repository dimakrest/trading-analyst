import { useState } from 'react';
import { Plus } from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '../../components/ui/button';
import {
  StockListsTable,
  CreateListDialog,
  EditListDialog,
  DeleteListDialog,
} from '../../components/stockLists';
import { useStockLists } from '../../hooks/useStockLists';
import type { StockList } from '../../services/stockListService';

/**
 * Extract user-friendly error message from various error types
 */
const extractErrorMessage = (err: unknown): string => {
  if (err && typeof err === 'object') {
    const axiosErr = err as { response?: { data?: { detail?: string } }; message?: string };
    if (axiosErr.response?.data?.detail) {
      return axiosErr.response.data.detail;
    }
    if (axiosErr.message) {
      return axiosErr.message;
    }
  }
  return 'An unexpected error occurred';
};

/**
 * Stock Lists management page
 *
 * Features:
 * - View all stock lists in a table
 * - Create new lists with name and optional symbols
 * - Edit existing lists (rename, add/remove symbols)
 * - Delete lists with confirmation
 * - Empty state when no lists exist
 * - Loading state while fetching
 */
export const StockLists = () => {
  const { lists, isLoading, error, createList, updateList, deleteList } = useStockLists();

  // Dialog states
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [editingList, setEditingList] = useState<StockList | null>(null);
  const [deletingList, setDeletingList] = useState<StockList | null>(null);

  // Submission states
  const [isCreating, setIsCreating] = useState(false);
  const [isUpdating, setIsUpdating] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  // Handlers
  const handleCreateList = async (data: { name: string; symbols?: string[] }) => {
    setIsCreating(true);
    try {
      await createList(data);
      toast.success(`List "${data.name}" created`);
    } catch (err) {
      toast.error(extractErrorMessage(err));
      throw err; // Re-throw to keep dialog open
    } finally {
      setIsCreating(false);
    }
  };

  const handleUpdateList = async (id: number, data: { name?: string; symbols?: string[] }) => {
    setIsUpdating(true);
    try {
      await updateList(id, data);
      toast.success('List updated');
    } catch (err) {
      toast.error(extractErrorMessage(err));
      throw err; // Re-throw to keep dialog open
    } finally {
      setIsUpdating(false);
    }
  };

  const handleDeleteList = async (list: StockList) => {
    setIsDeleting(true);
    try {
      await deleteList(list.id);
      toast.success(`List "${list.name}" deleted`);
    } catch (err) {
      toast.error(extractErrorMessage(err));
      throw err; // Re-throw to keep dialog open
    } finally {
      setIsDeleting(false);
    }
  };

  const handleEditClick = (list: StockList) => {
    setEditingList(list);
  };

  const handleDeleteClick = (list: StockList) => {
    setDeletingList(list);
  };

  // Calculate total symbols across all lists
  const totalSymbols = lists.reduce((sum, list) => sum + list.symbol_count, 0);

  return (
    <div className="flex-1 p-6 flex flex-col gap-5 max-w-[1200px] mx-auto w-full">
      {/* Page Header */}
      <div className="flex items-center justify-between gap-6">
        <div>
          <h1 className="font-display text-2xl font-bold tracking-tight text-text-primary">
            Stock Lists
          </h1>
          <p className="text-sm text-text-muted mt-1">
            Organize your symbols into watchlists for quick access
          </p>
        </div>
        <Button
          onClick={() => setCreateDialogOpen(true)}
          className="flex items-center gap-2"
        >
          <Plus className="w-[18px] h-[18px]" />
          Create List
        </Button>
      </div>

      {/* Lists Table */}
      <StockListsTable
        lists={lists}
        isLoading={isLoading}
        error={error}
        onEdit={handleEditClick}
        onDelete={handleDeleteClick}
        totalSymbols={totalSymbols}
      />

      {/* Create Dialog */}
      <CreateListDialog
        open={createDialogOpen}
        onOpenChange={setCreateDialogOpen}
        onSubmit={handleCreateList}
        isSubmitting={isCreating}
      />

      {/* Edit Dialog */}
      <EditListDialog
        list={editingList}
        open={editingList !== null}
        onOpenChange={(open) => !open && setEditingList(null)}
        onSubmit={handleUpdateList}
        isSubmitting={isUpdating}
      />

      {/* Delete Dialog */}
      <DeleteListDialog
        list={deletingList}
        open={deletingList !== null}
        onOpenChange={(open) => !open && setDeletingList(null)}
        onConfirm={handleDeleteList}
        isDeleting={isDeleting}
      />
    </div>
  );
};

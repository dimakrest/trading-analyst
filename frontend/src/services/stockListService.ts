import { apiClient } from '../lib/apiClient';

/**
 * Stock List entity
 */
export interface StockList {
  id: number;
  name: string;
  symbols: string[];
  symbol_count: number;
}

/**
 * Paginated response from the stock lists endpoint
 */
export interface StockListsResponse {
  items: StockList[];
  total: number;
  has_more: boolean;
}

/**
 * Request body for creating a new stock list
 */
export interface CreateStockListRequest {
  name: string;
  symbols?: string[];
}

/**
 * Request body for updating an existing stock list
 */
export interface UpdateStockListRequest {
  name?: string;
  symbols?: string[];
}

/**
 * Get all stock lists
 *
 * @returns Promise resolving to paginated stock lists response
 * @throws Error if the API request fails
 *
 * @example
 * const response = await stockListService.getLists();
 * console.log(`Found ${response.total} lists`);
 */
const getLists = async (): Promise<StockListsResponse> => {
  const response = await apiClient.get<StockListsResponse>('/v1/stock-lists');
  return response.data;
};

/**
 * Get a single stock list by ID
 *
 * @param id - Unique list identifier
 * @returns Promise resolving to the stock list details
 * @throws Error if the API request fails or list not found
 *
 * @example
 * const list = await stockListService.getList(1);
 * console.log(`List ${list.name} has ${list.symbol_count} symbols`);
 */
const getList = async (id: number): Promise<StockList> => {
  const response = await apiClient.get<StockList>(`/v1/stock-lists/${id}`);
  return response.data;
};

/**
 * Create a new stock list
 *
 * @param data - List name and optional initial symbols
 * @returns Promise resolving to the created stock list
 * @throws Error if the API request fails or validation fails
 *
 * @example
 * const newList = await stockListService.createList({
 *   name: 'Tech Leaders',
 *   symbols: ['AAPL', 'MSFT', 'GOOGL']
 * });
 */
const createList = async (data: CreateStockListRequest): Promise<StockList> => {
  const response = await apiClient.post<StockList>('/v1/stock-lists', data);
  return response.data;
};

/**
 * Update an existing stock list
 *
 * @param id - Unique list identifier
 * @param data - Fields to update (name and/or symbols)
 * @returns Promise resolving to the updated stock list
 * @throws Error if the API request fails or list not found
 *
 * @example
 * const updatedList = await stockListService.updateList(1, {
 *   name: 'Tech Giants',
 *   symbols: ['AAPL', 'MSFT', 'GOOGL', 'AMZN']
 * });
 */
const updateList = async (id: number, data: UpdateStockListRequest): Promise<StockList> => {
  const response = await apiClient.put<StockList>(`/v1/stock-lists/${id}`, data);
  return response.data;
};

/**
 * Delete a stock list
 *
 * @param id - Unique list identifier
 * @returns Promise resolving when deletion is complete
 * @throws Error if the API request fails or list not found
 *
 * @example
 * await stockListService.deleteList(1);
 */
const deleteList = async (id: number): Promise<void> => {
  await apiClient.delete(`/v1/stock-lists/${id}`);
};

export const stockListService = {
  getLists,
  getList,
  createList,
  updateList,
  deleteList,
};

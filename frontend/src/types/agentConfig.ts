import type { ScoringAlgorithm } from './live20';

/**
 * Agent Configuration entity
 */
export interface AgentConfig {
  id: number;
  name: string;
  agent_type: string;
  scoring_algorithm: ScoringAlgorithm;
  volume_score?: number;
  candle_pattern_score?: number;
  cci_score?: number;
  ma20_distance_score?: number;
}

/**
 * Response from GET /api/v1/agent-configs
 */
export interface AgentConfigListResponse {
  items: AgentConfig[];
  total: number;
}

/**
 * Request body for creating a new agent configuration
 */
export interface CreateAgentConfigRequest {
  name: string;
  agent_type?: string;
  scoring_algorithm?: ScoringAlgorithm;
  volume_score?: number;
  candle_pattern_score?: number;
  cci_score?: number;
  ma20_distance_score?: number;
}

/**
 * Request body for updating an existing agent configuration
 */
export interface UpdateAgentConfigRequest {
  name?: string;
  scoring_algorithm?: ScoringAlgorithm;
  volume_score?: number;
  candle_pattern_score?: number;
  cci_score?: number;
  ma20_distance_score?: number;
}

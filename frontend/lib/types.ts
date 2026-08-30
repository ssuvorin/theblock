export type VerificationStatus =
  | "verified_open_role"
  | "hiring_signal"
  | "unverified"
  | "stale";

export type EvidenceQuality = "sufficient" | "partial" | "insufficient";

export type RelationshipStatus = "active" | "cold" | "dormant" | "unknown";

export interface PublicCitation {
  url: string;
  title?: string;
  source_domain?: string;
  checked_at?: string;
  excerpt?: string;
  evidence_type?: string;
  verification_details?: Record<string, unknown>;
}

export interface PrivateCitation {
  interaction_id: string;
  source: string;
  subject?: string;
  occurred_at?: string;
  snippet?: string;
  locator?: string;
}

export interface WarmPathData {
  person_id: string;
  display_name: string;
  current_role?: string;
  path: string[];
  path_type?: string;
  relevance_reason?: string;
  suggested_action?: string;
  confidence_band?: "high" | "medium" | "low";
  relationship_status?: RelationshipStatus;
  ranking_factors?: Record<string, number>;
  strength_score?: number;
  private_citations: PrivateCitation[];
}

export interface Organization {
  id?: string;
  name: string;
  domain?: string;
  industry?: string;
  enrichment_provider?: string;
}

export interface Opportunity {
  id: string;
  opportunity_id: string;
  verification_status: VerificationStatus;
  role_title?: string;
  organization: Organization | null;
  location?: string;
  summary?: string;
  canonical_url?: string;
  source_domain?: string;
  checked_at?: string;
  goal_fit?: string;
  ranking_factors?: Record<string, string | number | boolean>;
  public_citations: PublicCitation[];
  warm_paths: WarmPathData[];
  warm_path_status?: string;
  warm_path_count?: number;
  saved?: boolean;
  dismissed?: boolean;
  provider?: string;
  provider_disclosure?: string;
}

export interface QueryGoal {
  role?: string;
  related_roles?: string[];
  industry?: string[];
  location?: string[];
  action?: string;
}

export interface NetworkCandidate {
  person_id: string;
  display_name: string;
  current_role?: string;
  relevance_reason?: string;
  private_citations?: Interaction[];
  relationship_strength?: number;
}

export interface QueryAnswer {
  summary: string;
  goal?: QueryGoal;
  search?: {
    provider?: string;
    country?: string;
    freshness?: string;
    checked_at?: string;
    credits_consumed?: number;
    cache_hit?: boolean;
    sources_checked?: number;
    disclosure?: string;
  };
  opportunities: Opportunity[];
  network_candidates?: NetworkCandidate[];
  evidence_quality: EvidenceQuality;
  degraded: boolean;
  degraded_components?: string[];
  private_retrieval?: string;
}

export interface QueryResponse {
  answer: QueryAnswer;
}

export interface PersonSummary {
  id: string;
  display_name: string;
  photo_url?: string | null;
  current_title?: string | null;
  current_org?: string | null;
  relationship_status?: RelationshipStatus;
  strength_score?: number;
  last_interaction_at?: string | null;
  tags?: string[];
  sources?: string[];
}

export interface PeopleResponse {
  people: PersonSummary[];
  total: number;
  page: number;
}

export interface Interaction {
  id: string;
  type: string;
  source: string;
  subject?: string;
  occurred_at: string;
  direction?: string;
  snippet?: string;
  body_text?: string;
}

export interface FollowUp {
  id: string;
  person_id?: string;
  person?: { id?: string; display_name?: string };
  reason: string;
  due_date?: string | null;
  priority?: string;
  status: "pending" | "done" | "skipped" | string;
  provenance?: string;
}

export interface PersonProfile extends Omit<PersonSummary, "current_org"> {
  current_org?: string | Organization | null;
  identities?: Array<{ kind: string; value: string; source?: string; verified?: boolean }>;
  employments?: Array<{ title: string; org: string; start?: string; current?: boolean }>;
  relationship?: {
    status?: string;
    strength_score?: number;
    strength_components?: Record<string, number>;
    last_interaction_at?: string;
    total_interactions?: number;
  };
  interactions?: Interaction[];
  documents?: Array<{ id: string; name: string; relationship_type?: string; url?: string }>;
  memory_facts?: Array<{ type: string; value: string; confidence?: string; status?: string }>;
  follow_ups?: FollowUp[];
  source_badges?: string[];
}

export interface PersonResponse {
  person: PersonProfile;
}

export interface Connection {
  id: string;
  source: string;
  external_account_id?: string;
  status: string;
  last_sync_at?: string | null;
  last_error?: string | null;
  capabilities?: Record<string, unknown>;
  item_count?: number;
}

export interface ConnectionsResponse {
  connections: Connection[];
}

export interface FollowUpsResponse {
  follow_ups: FollowUp[];
}

export interface Draft {
  text: string;
  person_id: string;
  opportunity_id: string;
  send_supported: false;
  apply_supported: false;
  allowed_actions: string[];
  private_citations: PrivateCitation[];
  public_citations: PublicCitation[];
  subject?: string;
  external_url?: string;
}

export interface DraftResponse {
  draft: Draft;
}

export interface OpportunitiesResponse {
  opportunities: Opportunity[];
  total: number;
  page: number;
}

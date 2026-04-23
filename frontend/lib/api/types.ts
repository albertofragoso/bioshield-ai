// Mirror of backend/app/schemas/models.py
// Keep in sync manually; CI validates with openapi-typescript against /openapi.json

export type RegulatoryStatus = "Approved" | "Banned" | "Restricted" | "Under Review";
export type SemaphoreColor = "GRAY" | "BLUE" | "YELLOW" | "ORANGE" | "RED";
export type ConflictSeverity = "HIGH" | "MEDIUM" | "LOW";
export type ConflictType = "REGULATORY" | "SCIENTIFIC" | "TEMPORAL";
export type ScanSource = "barcode" | "photo";

export interface RegisterRequest {
  email: string;
  password: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: "bearer";
  expires_in: number;
}

export interface UserResponse {
  id: string;
  email: string;
  created_at: string;
}

export interface BarcodeRequest {
  barcode: string;
}

export interface PhotoScanRequest {
  image_base64: string;
}

export interface IngredientConflict {
  conflict_type: ConflictType;
  severity: ConflictSeverity;
  summary: string;
  sources: string[];
}

export interface IngredientResult {
  name: string;
  canonical_name: string | null;
  cas_number: string | null;
  e_number: string | null;
  regulatory_status: RegulatoryStatus | null;
  confidence_score: number;
  conflicts: IngredientConflict[];
}

export interface ScanResponse {
  product_barcode: string;
  product_name: string | null;
  semaphore: SemaphoreColor;
  ingredients: IngredientResult[];
  conflict_severity: ConflictSeverity | null;
  source: ScanSource;
  scanned_at: string;
}

export interface BiomarkerUploadRequest {
  data: Record<string, number>;
}

export interface BiomarkerStatusResponse {
  id: string;
  uploaded_at: string;
  expires_at: string;
  has_data: boolean;
}

export interface ApiError {
  detail: string;
  status: number;
}

// OFF contribution (Fase 2 — flujo contributivo)
export interface OFFContributeRequest {
  barcode: string;
  ingredients: string[];
  image_base64?: string;
  consent: true;
  scan_history_id?: string;
}

export interface OFFContributeResponse {
  contribution_id: string;
  status: "PENDING" | "SUBMITTED" | "FAILED";
  message: string;
}

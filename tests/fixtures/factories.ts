// tests/fixtures/factories.ts
// Deterministic factories mirroring backend schemas.
// Style: arrow functions with Partial<T> overrides, no randomization.

import type {
  Biomarker,
  BiomarkerExtractionResult,
  BiomarkerStatusResponse,
  BiomarkerUploadRequest,
  IngredientConflict,
  IngredientResult,
  PersonalizedInsight,
  ScanHistoryEntry,
  ScanResponse,
  TokenResponse,
  UserResponse,
} from "../../frontend/lib/api/types";

const FIXED_NOW = "2026-04-28T12:00:00Z";
const FIXED_USER_ID = "00000000-0000-4000-8000-000000000001";
const FIXED_BIOSYNC_ID = "00000000-0000-4000-8000-000000000002";

export const NUTELLA_BARCODE = "3017620422003";
export const TEST_EMAIL = "test@bioshield.dev";
export const TEST_PASSWORD = "Test1234!";

export const makeUser = (overrides: Partial<UserResponse> = {}): UserResponse => ({
  id: FIXED_USER_ID,
  email: TEST_EMAIL,
  created_at: FIXED_NOW,
  ...overrides,
});

export const makeTokenResponse = (overrides: Partial<TokenResponse> = {}): TokenResponse => ({
  access_token: "fake.access.token",
  refresh_token: "fake.refresh.token",
  token_type: "bearer",
  expires_in: 900,
  ...overrides,
});

export const makeConflict = (overrides: Partial<IngredientConflict> = {}): IngredientConflict => ({
  conflict_type: "REGULATORY",
  severity: "MEDIUM",
  summary: "Banned in EU since 2018",
  sources: ["EFSA 2018-04-12"],
  ...overrides,
});

export const makeIngredient = (overrides: Partial<IngredientResult> = {}): IngredientResult => ({
  name: "Aceite de palma",
  canonical_name: "palm_oil",
  cas_number: "8002-75-3",
  e_number: null,
  regulatory_status: "Restricted",
  confidence_score: 0.92,
  conflicts: [],
  ...overrides,
});

export const makeBiomarker = (overrides: Partial<Biomarker> = {}): Biomarker => ({
  name: "ldl",
  raw_name: "LDL Colesterol",
  value: 95,
  unit: "mg/dL",
  unit_normalized: true,
  reference_range_low: 0,
  reference_range_high: 100,
  reference_source: "canonical",
  classification: "normal",
  ...overrides,
});

export const makePersonalizedInsight = (
  overrides: Partial<PersonalizedInsight> = {},
): PersonalizedInsight => ({
  biomarker_name: "ldl",
  biomarker_value: 150,
  biomarker_unit: "mg/dL",
  classification: "high",
  affecting_ingredients: ["Grasas trans", "Aceite de palma"],
  severity: "HIGH",
  kind: "alert",
  impact_direction: "raises",
  reference_range_low: 0,
  reference_range_high: 100,
  friendly_title: "Tu LDL está alto y este producto lo empeora",
  friendly_biomarker_label: "Colesterol LDL",
  friendly_explanation: "Tu LDL está en 150 mg/dL (rango normal: <100). Las grasas trans elevan el LDL.",
  friendly_recommendation: "Evita este producto o consume con moderación.",
  avatar_variant: "orange",
  ...overrides,
});

export const makeScanResponse = (overrides: Partial<ScanResponse> = {}): ScanResponse => ({
  product_barcode: NUTELLA_BARCODE,
  product_name: "Nutella",
  semaphore: "YELLOW",
  ingredients: [makeIngredient()],
  conflict_severity: "MEDIUM",
  source: "barcode",
  scanned_at: FIXED_NOW,
  personalized_insights: [],
  ...overrides,
});

export const makeScanHistoryEntry = (
  overrides: Partial<ScanHistoryEntry> = {},
): ScanHistoryEntry => ({
  id: "scan-1",
  product_barcode: NUTELLA_BARCODE,
  product_name: "Nutella",
  semaphore: "YELLOW",
  conflict_severity: "MEDIUM",
  source: "barcode",
  scanned_at: FIXED_NOW,
  ...overrides,
});

export const makeBiomarkerStatus = (
  overrides: Partial<BiomarkerStatusResponse> = {},
): BiomarkerStatusResponse => ({
  id: FIXED_BIOSYNC_ID,
  uploaded_at: FIXED_NOW,
  expires_at: "2026-10-25T12:00:00Z",
  has_data: true,
  ...overrides,
});

export const makeBiomarkerExtraction = (
  overrides: Partial<BiomarkerExtractionResult> = {},
): BiomarkerExtractionResult => ({
  biomarkers: [makeBiomarker()],
  lab_name: "Lab Bioquímico Demo",
  test_date: "2026-04-20",
  language: "es",
  ...overrides,
});

export const makeBiomarkerUpload = (
  overrides: Partial<BiomarkerUploadRequest> = {},
): BiomarkerUploadRequest => ({
  biomarkers: [makeBiomarker()],
  lab_name: "Lab Bioquímico Demo",
  test_date: "2026-04-20",
  ...overrides,
});

export const makeOrangeBiomarkerScan = (): ScanResponse =>
  makeScanResponse({
    semaphore: "ORANGE",
    conflict_severity: "HIGH",
    ingredients: [
      makeIngredient({
        name: "Grasas trans",
        canonical_name: "trans_fats",
        regulatory_status: "Banned",
        conflicts: [makeConflict({ severity: "HIGH", summary: "Banned in many jurisdictions" })],
      }),
      makeIngredient({
        name: "Aceite de palma",
        canonical_name: "palm_oil",
        regulatory_status: "Restricted",
      }),
    ],
    personalized_insights: [makePersonalizedInsight()],
  });

export const makeMixedHistory = (): ScanHistoryEntry[] => [
  makeScanHistoryEntry({ id: "s1", semaphore: "RED", scanned_at: "2026-04-28T10:00:00Z" }),
  makeScanHistoryEntry({ id: "s2", semaphore: "YELLOW", scanned_at: "2026-04-28T08:00:00Z" }),
  makeScanHistoryEntry({ id: "s3", semaphore: "BLUE", scanned_at: "2026-04-27T15:00:00Z" }),
  makeScanHistoryEntry({ id: "s4", semaphore: "ORANGE", scanned_at: "2026-04-25T12:00:00Z" }),
];

export const makeOFFContributeResponse = (
  overrides: Partial<import("../../frontend/lib/api/types").OFFContributeResponse> = {},
): import("../../frontend/lib/api/types").OFFContributeResponse => ({
  contribution_id: "contrib-00000000-0001",
  status: "PENDING",
  message: "Contribution received and queued",
  ...overrides,
});

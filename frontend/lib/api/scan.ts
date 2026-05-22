import { apiFetch } from "./client";
import type {
  AlternativesResponse,
  IngredientResult,
  OFFContributeRequest,
  OFFContributeResponse,
  PersonalizedInsight,
  ScanResponse,
  ScanHistoryEntry,
  LinkBarcodeRequest,
} from "./types";

export interface ShareLinkResponse {
  share_url: string;
  expires_at: string;
}

export interface ScanShareProjection {
  product_name: string | null;
  product_barcode: string;
  semaphore: string;
  ingredients: IngredientResult[];
  conflict_severity: string | null;
  scanned_at: string;
  personalized_insights: PersonalizedInsight[];
}

export async function scanBarcode(barcode: string): Promise<ScanResponse> {
  return apiFetch<ScanResponse>("/scan/barcode", {
    method: "POST",
    body: JSON.stringify({ barcode }),
  });
}

export async function scanPhoto(image_base64: string): Promise<ScanResponse> {
  return apiFetch<ScanResponse>("/scan/photo", {
    method: "POST",
    body: JSON.stringify({ image_base64 }),
  });
}

export async function contributeToOff(body: OFFContributeRequest): Promise<OFFContributeResponse> {
  return apiFetch<OFFContributeResponse>("/scan/contribute", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function getScanHistory(limit = 5): Promise<ScanHistoryEntry[]> {
  return apiFetch<ScanHistoryEntry[]>(`/scan/history?limit=${limit}`);
}

export async function getScanResult(barcode: string): Promise<ScanResponse> {
  return apiFetch<ScanResponse>(`/scan/result/${barcode}`);
}

export async function getAlternatives(barcode: string): Promise<AlternativesResponse> {
  return apiFetch<AlternativesResponse>(`/scan/alternatives/${barcode}`);
}

export async function linkPhotoToBarcode(
  pseudoBarcode: string,
  barcode: string
): Promise<ScanResponse> {
  return apiFetch<ScanResponse>(`/scan/photo/${pseudoBarcode}/link`, {
    method: "POST",
    body: JSON.stringify({ barcode } satisfies LinkBarcodeRequest),
  });
}

export async function createShareLink(scanDbId: string): Promise<ShareLinkResponse> {
  return apiFetch<ShareLinkResponse>(`/scan/${scanDbId}/share`, {
    method: "POST",
  });
}

export async function revokeShareLink(scanDbId: string): Promise<void> {
  return apiFetch<void>(`/scan/${scanDbId}/share`, {
    method: "DELETE",
  });
}

export async function getSharedScan(token: string): Promise<ScanShareProjection> {
  const res = await fetch(`/api/scan/share/${token}`);
  if (res.status === 410) throw new Error("EXPIRED");
  if (!res.ok) throw new Error(`Shared scan fetch failed: ${res.status}`);
  return res.json();
}

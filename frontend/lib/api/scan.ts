import { apiFetch } from "./client";
import type { OFFContributeRequest, OFFContributeResponse, ScanResponse } from "./types";

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

import { apiFetch } from "./client";
import type { BiomarkerStatusResponse, BiomarkerUploadRequest } from "./types";

export async function uploadBiomarkers(body: BiomarkerUploadRequest): Promise<BiomarkerStatusResponse> {
  return apiFetch<BiomarkerStatusResponse>("/biosync/upload", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function getBiomarkerStatus(): Promise<BiomarkerStatusResponse> {
  return apiFetch<BiomarkerStatusResponse>("/biosync/status");
}

export async function deleteBiomarkers(): Promise<void> {
  return apiFetch<void>("/biosync/data", { method: "DELETE" });
}

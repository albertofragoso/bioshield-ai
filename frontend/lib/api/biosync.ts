import { apiFetch } from "./client";
import type { BiomarkerExtractionResult, BiomarkerStatusResponse, BiomarkerUploadRequest } from "./types";

export async function extractBiomarkers(file: File): Promise<BiomarkerExtractionResult> {
  const form = new FormData();
  form.append("file", file);
  return apiFetch<BiomarkerExtractionResult>("/biosync/extract", {
    method: "POST",
    body: form,
  });
}

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

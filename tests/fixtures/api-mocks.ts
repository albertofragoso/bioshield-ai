// tests/fixtures/api-mocks.ts
// Reusable page.route() helpers. Each helper intercepts one or more endpoints.
// Mock first, navigate after — always call these before page.goto().

import type { Page, Route } from "@playwright/test";
import {
  makeBiomarkerExtraction,
  makeBiomarkerStatus,
  makeOFFContributeResponse,
  makeScanHistoryEntry,
  makeScanResponse,
  makeTokenResponse,
  makeUser,
} from "./factories";
import type {
  BiomarkerExtractionResult,
  BiomarkerStatusResponse,
  OFFContributeResponse,
  ScanHistoryEntry,
  ScanResponse,
} from "../../frontend/lib/api/types";

const json = (route: Route, status: number, body: unknown) =>
  route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });

// ── Auth ─────────────────────────────────────────────────────────────────────

export async function mockAuthLoginSuccess(page: Page) {
  await page.route("**/auth/login", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      headers: {
        "Set-Cookie": [
          "access_token=fake.access; Path=/; HttpOnly; SameSite=Lax",
          "refresh_token=fake.refresh; Path=/; HttpOnly; SameSite=Lax",
        ].join(", "),
      },
      body: JSON.stringify(makeTokenResponse()),
    });
  });
}

export async function mockAuthLoginFail(page: Page, status: 401 | 429 = 401) {
  await page.route("**/auth/login", (route) =>
    json(route, status, {
      detail: status === 401 ? "Credenciales inválidas" : "Demasiados intentos. Espera 60s.",
    }),
  );
}

export async function mockAuthRegisterSuccess(page: Page) {
  await page.route("**/auth/register", (route) => json(route, 201, makeUser()));
}

export async function mockAuthRegisterConflict(page: Page) {
  await page.route("**/auth/register", (route) =>
    json(route, 409, { detail: "Este correo ya está registrado" }),
  );
}

export async function mockAuthRefreshSuccess(page: Page) {
  await page.route("**/auth/refresh", (route) => json(route, 200, makeTokenResponse()));
}

export async function mockAuthRefreshFail(page: Page) {
  await page.route("**/auth/refresh", (route) =>
    json(route, 401, { detail: "Refresh token inválido" }),
  );
}

export async function mockAuthLogout(page: Page) {
  await page.route("**/auth/logout", (route) =>
    route.fulfill({
      status: 204,
      headers: {
        "Set-Cookie": [
          "access_token=; Path=/; HttpOnly; Max-Age=0",
          "refresh_token=; Path=/; HttpOnly; Max-Age=0",
        ].join(", "),
      },
    }),
  );
}

// ── Scan ─────────────────────────────────────────────────────────────────────

export async function mockScanBarcode(
  page: Page,
  response: ScanResponse = makeScanResponse(),
) {
  await page.route("**/scan/barcode", (route) => json(route, 200, response));
}

export async function mockScanBarcodeError(page: Page, status: 404 | 500) {
  await page.route("**/scan/barcode", (route) =>
    json(route, status, {
      detail: status === 404 ? "Producto no encontrado" : "Error interno del servidor",
    }),
  );
}

export async function mockScanPhoto(
  page: Page,
  response: ScanResponse = makeScanResponse({ source: "photo", product_barcode: "photo-abc123def456" }),
) {
  await page.route("**/scan/photo", (route) => json(route, 200, response));
}

export async function mockScanPhotoError(page: Page, status: 413 | 422) {
  await page.route("**/scan/photo", (route) =>
    json(route, status, {
      detail: status === 413 ? "Imagen demasiado grande" : "Imagen inválida",
    }),
  );
}

export async function mockScanResultGet(page: Page, response: ScanResponse) {
  const barcode = response.product_barcode;
  await page.route(`**/scan/result/${barcode}`, (route) => json(route, 200, response));
}

export async function mockScanHistory(
  page: Page,
  entries: ScanHistoryEntry[] = [makeScanHistoryEntry()],
) {
  await page.route(/\/scan\/history(\?.*)?$/, (route) => json(route, 200, entries));
}

export async function mockContributeOff(
  page: Page,
  response: OFFContributeResponse = makeOFFContributeResponse(),
) {
  await page.route("**/scan/contribute", (route) => json(route, 202, response));
}

export async function mockContributeOffError(page: Page) {
  await page.route("**/scan/contribute", (route) =>
    json(route, 500, { detail: "Error interno del servidor" }),
  );
}

// ── Biosync ──────────────────────────────────────────────────────────────────

export async function mockBiosyncExtract(
  page: Page,
  result: BiomarkerExtractionResult = makeBiomarkerExtraction(),
) {
  await page.route("**/biosync/extract", (route) => json(route, 200, result));
}

export async function mockBiosyncExtractError(page: Page, status: 413 | 422) {
  await page.route("**/biosync/extract", (route) =>
    json(route, status, {
      detail: status === 413 ? "PDF demasiado grande" : "Archivo inválido",
    }),
  );
}

export async function mockBiosyncUpload(
  page: Page,
  response: BiomarkerStatusResponse = makeBiomarkerStatus(),
) {
  await page.route("**/biosync/upload", (route) => json(route, 201, response));
}

export async function mockBiosyncStatus(
  page: Page,
  status: BiomarkerStatusResponse | null = makeBiomarkerStatus(),
) {
  await page.route("**/biosync/status", (route) =>
    status === null
      ? json(route, 404, { detail: "No biomarkers" })
      : json(route, 200, status),
  );
}

export async function mockBiosyncDelete(page: Page) {
  await page.route("**/biosync/data", (route) => route.fulfill({ status: 204 }));
}

// ── Default mock layer ────────────────────────────────────────────────────────

/** Apply sensible defaults for signed-in (app) pages. Call inside mockedPage fixture. */
export async function applyDefaultMocks(page: Page) {
  await mockAuthRefreshSuccess(page);
  await mockAuthLogout(page);
  await mockBiosyncStatus(page, null);
  await mockScanHistory(page, []);
}

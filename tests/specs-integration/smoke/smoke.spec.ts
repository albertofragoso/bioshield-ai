// tests/specs-integration/smoke/smoke.spec.ts
import { test, expect } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';

const BACKEND = 'http://localhost:8000';
const NUTELLA_BARCODE = '3017624010701';
const VALID_SEMAPHORES = ['RED', 'ORANGE', 'YELLOW', 'GRAY'];

// All requests use context.request to inherit the storageState cookies
// from tests/fixtures/integration-auth.json (set in playwright.config.ts)

test('1 — auth state is valid', async ({ context }) => {
  const res = await context.request.get(`${BACKEND}/scan/ping`);
  expect(res.status()).toBe(200);
  const body = await res.json();
  expect(body).toHaveProperty('user_id');
  expect(typeof body.user_id).toBe('string');
});

test('2 — scan barcode Nutella → semáforo válido', async ({ context }) => {
  const res = await context.request.post(`${BACKEND}/scan/barcode`, {
    data: { barcode: NUTELLA_BARCODE },
  });
  expect(res.status()).toBe(200);
  const body = await res.json();
  expect(VALID_SEMAPHORES).toContain(body.semaphore);
  expect(body.product_name).toBeTruthy();
  expect(Array.isArray(body.ingredients)).toBe(true);
  expect(body.ingredients.length).toBeGreaterThan(0);
  expect(body.product_barcode).toBe(NUTELLA_BARCODE);
});

test('3 — biosync: extract → upload → status', async ({ context }) => {
  const pdfPath = path.join(process.cwd(), 'tests/fixtures/biosync-test.pdf');
  const pdfBuffer = fs.readFileSync(pdfPath);

  // 3a. Extract biomarkers from PDF
  const extractRes = await context.request.post(`${BACKEND}/biosync/extract`, {
    multipart: {
      file: {
        name: 'biosync-test.pdf',
        mimeType: 'application/pdf',
        buffer: pdfBuffer,
      },
    },
  });
  expect(extractRes.status()).toBe(200);
  const extracted = await extractRes.json();
  expect(Array.isArray(extracted.biomarkers)).toBe(true);
  expect(extracted.biomarkers.length).toBeGreaterThan(0);

  // 3b. Upload (persist with AES-256 encryption)
  const uploadRes = await context.request.post(`${BACKEND}/biosync/upload`, {
    data: { biomarkers: extracted.biomarkers },
  });
  expect(uploadRes.status()).toBe(201);
  const uploaded = await uploadRes.json();
  expect(uploaded.has_data).toBe(true);

  // 3c. Status confirms persistence
  const statusRes = await context.request.get(`${BACKEND}/biosync/status`);
  expect(statusRes.status()).toBe(200);
  const status = await statusRes.json();
  expect(status.has_data).toBe(true);
  expect(new Date(status.expires_at).getTime()).toBeGreaterThan(Date.now());
});

test('4 — resultado guardado del scan', async ({ context }) => {
  const res = await context.request.get(`${BACKEND}/scan/result/${NUTELLA_BARCODE}`);
  expect(res.status()).toBe(200);
  const body = await res.json();
  expect(body.product_barcode).toBe(NUTELLA_BARCODE);
  expect(VALID_SEMAPHORES).toContain(body.semaphore);
  expect(Array.isArray(body.ingredients)).toBe(true);
});

test('5 — historial de scans', async ({ context }) => {
  const res = await context.request.get(`${BACKEND}/scan/history`);
  expect(res.status()).toBe(200);
  const body = await res.json();
  expect(Array.isArray(body)).toBe(true);
  expect(body.length).toBeGreaterThan(0);
  const nutellaEntry = body.find(
    (e: { product_barcode: string }) => e.product_barcode === NUTELLA_BARCODE,
  );
  expect(nutellaEntry).toBeDefined();
  expect(VALID_SEMAPHORES).toContain(nutellaEntry.semaphore);
});

test('6 — logout revoca la sesión', async ({ context }) => {
  // Logout
  const logoutRes = await context.request.post(`${BACKEND}/auth/logout`);
  expect(logoutRes.status()).toBe(204);

  // Any auth-required endpoint must now return 401
  const verifyRes = await context.request.get(`${BACKEND}/scan/ping`);
  expect(verifyRes.status()).toBe(401);
});

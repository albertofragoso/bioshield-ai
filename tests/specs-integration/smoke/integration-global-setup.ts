// tests/specs-integration/smoke/integration-global-setup.ts
import { test, expect } from '@playwright/test';
import { execSync } from 'child_process';

const BACKEND = 'http://localhost:8000';
const AUTH_FILE = 'tests/fixtures/integration-auth.json';
const TEST_EMAIL = 'integration-test@bioshield.test';
const TEST_PASSWORD = 'Integration!2026';

test('setup: start docker stack and seed test user', async ({ browser }) => {
  test.setTimeout(300_000); // 5 min — docker pull + build + alembic migrations

  // 1. Start the full Docker stack
  execSync(
    'docker compose -f docker-compose.integration.yml up -d --wait',
    { stdio: 'inherit', timeout: 180_000 },
  );

  // 2. Wait for backend health (alembic migrations may add latency after --wait)
  await waitForBackend(BACKEND + '/health');

  // 3. Create browser context for cookie-aware API calls
  const context = await browser.newContext();

  // 4. Register test user (409 = already exists from a partial run — that's fine)
  const registerRes = await context.request.post(BACKEND + '/auth/register', {
    data: { email: TEST_EMAIL, password: TEST_PASSWORD },
  });
  expect([201, 409]).toContain(registerRes.status());

  // 5. Login and capture cookies
  const loginRes = await context.request.post(BACKEND + '/auth/login', {
    data: { email: TEST_EMAIL, password: TEST_PASSWORD },
  });
  expect(loginRes.status()).toBe(200);

  // 6. Save storageState (cookies) for smoke tests
  await context.storageState({ path: AUTH_FILE });
  await context.close();
});

async function waitForBackend(url: string, retries = 24, intervalMs = 3_000): Promise<void> {
  for (let i = 0; i < retries; i++) {
    try {
      const res = await fetch(url);
      if (res.ok) return;
    } catch {
      // not ready yet
    }
    await new Promise((r) => setTimeout(r, intervalMs));
  }
  throw new Error(`Backend at ${url} did not become healthy after ${retries} retries`);
}

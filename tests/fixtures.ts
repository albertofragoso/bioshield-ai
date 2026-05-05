import { test as base, expect, Page } from '@playwright/test';

// Test credentials
export const TEST_EMAIL = 'test@example.com';
export const TEST_PASSWORD = 'TestPassword123!';
export const NUTELLA_BARCODE = '3017620422003';

// Custom fixture type
type MockedPageFixture = {
  mockedPage: Page;
};

// Create extended test with mockedPage fixture
export const test = base.extend<MockedPageFixture>({
  mockedPage: async ({ page, context }, use) => {
    // Setup: apply default mocks to every test
    await applyDefaultMocks(page);

    // Setup auth cookies for authenticated pages
    await context.addCookies([
      {
        name: 'access_token',
        value: 'test-jwt-token',
        domain: 'localhost',
        path: '/',
        httpOnly: true,
        sameSite: 'Lax',
      },
      {
        name: 'refresh_token',
        value: 'test-refresh-token',
        domain: 'localhost',
        path: '/',
        httpOnly: true,
        sameSite: 'Lax',
      },
    ]);

    await use(page);
    // Teardown if needed
  },
});

// Export expect and test
export { expect };

// Default mocks applied to every test
async function applyDefaultMocks(page: Page) {
  // Mock auth endpoints with JWT cookies
  await page.route('**/auth/login', (route) => {
    route.abort();
  });

  await page.route('**/auth/register', (route) => {
    route.abort();
  });

  // Mock GET /auth/me for session validation
  await page.route('**/auth/me', (route) => {
    route.fulfill({
      status: 200,
      body: JSON.stringify({
        id: 'test-user-id',
        email: TEST_EMAIL,
        created_at: new Date().toISOString(),
      }),
    });
  });

  await page.route('**/biosync/status', (route) => {
    route.fulfill({
      status: 404,
      body: JSON.stringify({ detail: 'No biomarkers' }),
    });
  });

  await page.route('**/scan/history', (route) => {
    route.fulfill({
      status: 200,
      body: JSON.stringify([]),
    });
  });
}

// ============ Auth Mocks ============
export async function mockAuthLoginSuccess(page: Page) {
  await page.route('**/auth/login', (route) => {
    route.fulfill({
      status: 200,
      body: JSON.stringify({
        access_token: 'test-jwt-token',
        refresh_token: 'test-refresh-token',
        token_type: 'bearer',
        expires_in: 1800,
      }),
      headers: {
        'set-cookie': 'access_token=test-jwt-token; HttpOnly; Path=/',
      },
    });
  });
}

export async function mockAuthLoginFail(page: Page, statusCode: number) {
  await page.route('**/auth/login', (route) => {
    const messages = {
      401: { detail: 'Credenciales inválidas' },
      429: { detail: 'Demasiados intentos. Espera 60s.' },
    };
    route.fulfill({
      status: statusCode,
      body: JSON.stringify(messages[statusCode] || { detail: 'Error' }),
    });
  });
}

export async function mockAuthRegisterSuccess(page: Page) {
  await page.route('**/auth/register', (route) => {
    route.fulfill({
      status: 201,
      body: JSON.stringify({
        id: 'test-user-id',
        email: TEST_EMAIL,
        created_at: new Date().toISOString(),
      }),
    });
  });

  await mockAuthLoginSuccess(page);
}

export async function mockAuthRegisterFail(page: Page, statusCode: number) {
  const messages = {
    409: { detail: 'Este correo ya está registrado' },
    422: { detail: 'Validación fallida' },
  };
  await page.route('**/auth/register', (route) => {
    route.fulfill({
      status: statusCode,
      body: JSON.stringify(messages[statusCode] || { detail: 'Error' }),
    });
  });
}

export async function mockAuthRegisterConflict(page: Page) {
  await mockAuthRegisterFail(page, 409);
}

export async function mockAuthLogout(page: Page) {
  await page.route('**/auth/logout', (route) => {
    route.fulfill({
      status: 204,
      body: '',
    });
  });
}

export async function mockAuthRefresh(page: Page) {
  await page.route('**/auth/refresh', (route) => {
    route.fulfill({
      status: 200,
      body: JSON.stringify({
        access_token: 'new-jwt-token',
        refresh_token: 'new-refresh-token',
        token_type: 'bearer',
        expires_in: 1800,
      }),
    });
  });
}

export const mockAuthRefreshSuccess = mockAuthRefresh;

export async function mockAuthRefreshFail(page: Page) {
  await page.route('**/auth/refresh', (route) => {
    route.fulfill({
      status: 401,
      body: JSON.stringify({ detail: 'Sesión expirada' }),
    });
  });
}

// ============ Scan Mocks ============
export async function mockScanBarcode(page: Page, barcode: string = '3017620422003') {
  await page.route('**/scan/barcode', (route) => {
    route.fulfill({
      status: 200,
      body: JSON.stringify({
        product_barcode: barcode,
        product_name: 'Nutella',
        semaphore: 'YELLOW',
        conflict_severity: 'LOW',
        source: 'barcode',
        scanned_at: new Date().toISOString(),
        ingredients: [
          {
            name: 'Sucralose',
            canonical_name: 'Sucralose',
            e_number: 'E955',
            regulatory_status: 'Approved',
            confidence_score: 0.95,
            conflicts: [],
          },
        ],
      }),
    });
  });
}

export async function mockScanPhoto(page: Page) {
  await page.route('**/scan/photo', (route) => {
    route.fulfill({
      status: 200,
      body: JSON.stringify({
        product_barcode: 'photo-abc123',
        product_name: 'Producto Etiqueta',
        semaphore: 'BLUE',
        conflict_severity: null,
        source: 'photo',
        scanned_at: new Date().toISOString(),
        ingredients: [
          {
            name: 'Sugar',
            canonical_name: 'Sugar',
            e_number: null,
            regulatory_status: 'Approved',
            confidence_score: 0.9,
            conflicts: [],
          },
        ],
      }),
    });
  });
}

export async function mockScanBarcodeNotFound(page: Page) {
  await page.route('**/scan/barcode', (route) => {
    route.fulfill({
      status: 404,
      body: JSON.stringify({ detail: 'Producto no encontrado' }),
    });
  });
}

export async function mockScanBarcodeError(page: Page, statusCode: number) {
  const messages: Record<number, any> = {
    404: { detail: 'Producto no encontrado' },
    500: { detail: 'Error procesando barcode' },
  };
  await page.route('**/scan/barcode', (route) => {
    route.fulfill({
      status: statusCode,
      body: JSON.stringify(messages[statusCode] || { detail: 'Error' }),
    });
  });
}

export async function mockScanResult(page: Page, barcode: string, semaphore: string = 'BLUE') {
  await page.route(`**/scan/result/**`, (route) => {
    route.fulfill({
      status: 200,
      body: JSON.stringify({
        product_barcode: barcode,
        product_name: 'Test Product',
        semaphore,
        conflict_severity: null,
        source: 'barcode',
        scanned_at: new Date().toISOString(),
        ingredients: [],
      }),
    });
  });
}

export async function mockScanContribute(page: Page) {
  await page.route('**/scan/contribute', (route) => {
    route.fulfill({
      status: 202,
      body: JSON.stringify({
        contribution_id: 'contrib-123',
        status: 'PENDING',
        message: 'Contribución enviada a Open Food Facts',
      }),
    });
  });
}

// ============ Biosync Mocks ============
export function makeBiomarkerStatus(overrides = {}) {
  return {
    id: 'biomarker-id',
    uploaded_at: new Date().toISOString(),
    expires_at: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString(),
    has_data: true,
    ...overrides,
  };
}

export async function mockBiosyncStatus(page: Page, status: any) {
  if (status === null) {
    await page.route('**/biosync/status', (route) => {
      route.fulfill({
        status: 404,
        body: JSON.stringify({ detail: 'No biomarkers' }),
      });
    });
  } else {
    await page.route('**/biosync/status', (route) => {
      route.fulfill({
        status: 200,
        body: JSON.stringify(status || makeBiomarkerStatus()),
      });
    });
  }
}

export async function mockBiosyncExtract(page: Page, biomarkers: any[] = []) {
  await page.route('**/biosync/extract', (route) => {
    route.fulfill({
      status: 200,
      body: JSON.stringify({
        biomarkers: biomarkers.length > 0 ? biomarkers : [
          { name: 'ldl', raw_name: 'LDL', value: 150, unit: 'mg/dL', reference_range_low: 0, reference_range_high: 100 },
        ],
        lab_name: 'Chopo',
        test_date: new Date().toISOString(),
        language: 'es',
      }),
    });
  });
}

export async function mockBiosyncExtractError(page: Page, statusCode: number) {
  await page.route('**/biosync/extract', (route) => {
    route.fulfill({
      status: statusCode,
      body: JSON.stringify({ detail: 'Error' }),
    });
  });
}

export async function mockBiosyncUpload(page: Page) {
  await page.route('**/biosync/upload', (route) => {
    route.fulfill({
      status: 201,
      body: JSON.stringify(makeBiomarkerStatus()),
    });
  });
}

export async function mockBiosyncDelete(page: Page) {
  await page.route('**/biosync/data', (route) => {
    route.fulfill({
      status: 204,
      body: '',
    });
  });
}

// ============ Dashboard & History Mocks ============
export function makeScanHistoryEntry(overrides = {}) {
  return {
    id: 'scan-1',
    product_barcode: '3017620422003',
    product_name: 'Nutella',
    semaphore: 'YELLOW',
    conflict_severity: 'LOW',
    source: 'barcode',
    scanned_at: new Date().toISOString(),
    ...overrides,
  };
}

export async function mockScanHistory(page: Page, entries: any[] = []) {
  const defaultEntries = [
    makeScanHistoryEntry({ id: 'scan-1', product_name: 'Nutella', semaphore: 'YELLOW' }),
    makeScanHistoryEntry({ id: 'scan-2', product_barcode: 'photo-abc123', product_name: 'Producto Etiqueta', semaphore: 'BLUE', source: 'photo' }),
  ];

  await page.route('**/scan/history', (route) => {
    route.fulfill({
      status: 200,
      body: JSON.stringify(entries.length > 0 ? entries : defaultEntries),
    });
  });
}

export async function mockDashboardData(page: Page) {
  await mockBiosyncStatus(page, makeBiomarkerStatus({ has_data: true }));
  await mockScanHistory(page);
}

// ============ Helper Builders ============
export function makeIngredient(overrides = {}) {
  return {
    name: 'Sugar',
    canonical_name: 'Sugar',
    cas_number: null,
    e_number: null,
    regulatory_status: 'Approved',
    confidence_score: 0.9,
    conflicts: [],
    ...overrides,
  };
}

export function makeConflict(overrides = {}) {
  return {
    conflict_type: 'REGULATORY',
    severity: 'HIGH',
    summary: 'Banned in EFSA',
    sources: ['EFSA'],
    ...overrides,
  };
}

export function makeBiomarker(overrides = {}) {
  return {
    name: 'ldl',
    raw_name: 'LDL Colesterol',
    value: 150,
    unit: 'mg/dL',
    unit_normalized: true,
    reference_range_low: 0,
    reference_range_high: 100,
    reference_source: 'lab',
    classification: 'high',
    ...overrides,
  };
}

export function makeBiomarkerExtraction(overrides = {}) {
  return {
    biomarkers: [makeBiomarker()],
    lab_name: 'Chopo',
    test_date: new Date().toISOString(),
    language: 'es',
    ...overrides,
  };
}

export function makePersonalizedInsight(overrides = {}) {
  return {
    biomarker_name: 'ldl',
    biomarker_value: 150,
    biomarker_unit: 'mg/dL',
    classification: 'high',
    kind: 'alert',
    impact_direction: 'raises',
    affecting_ingredients: ['Trans fat', 'Palm oil'],
    severity: 'HIGH',
    reference_range_low: 0,
    reference_range_high: 100,
    friendly_title: 'LDL elevado',
    friendly_biomarker_label: 'Colesterol LDL',
    friendly_explanation: 'Tu LDL está elevado...',
    friendly_recommendation: 'Evita grasas trans...',
    avatar_variant: 'orange',
    ...overrides,
  };
}

export function makeScanResponse(overrides = {}) {
  return {
    product_barcode: '3017620422003',
    product_name: 'Nutella',
    semaphore: 'BLUE',
    conflict_severity: null,
    source: 'barcode',
    scanned_at: new Date().toISOString(),
    ingredients: [],
    personalized_insights: [],
    ...overrides,
  };
}

export function makeOrangeBiomarkerScan(overrides = {}) {
  return makeScanResponse({
    semaphore: 'ORANGE',
    conflict_severity: 'HIGH',
    ingredients: [
      makeIngredient({ name: 'Trans fat', regulatory_status: 'Restricted' }),
      makeIngredient({ name: 'Palm oil', regulatory_status: 'Approved' }),
    ],
    personalized_insights: [
      makePersonalizedInsight({
        biomarker_name: 'ldl',
        affecting_ingredients: ['Trans fat', 'Palm oil'],
      }),
    ],
    ...overrides,
  });
}

// ============ Additional Missing Mocks ============
export async function mockScanResultGet(page: Page, scanResponse: any) {
  const barcode = scanResponse.product_barcode;
  await page.route(`**/scan/result/${barcode}`, (route) => {
    route.fulfill({
      status: 200,
      body: JSON.stringify(scanResponse),
    });
  });
}

export async function mockContributeOff(page: Page) {
  await page.route('**/scan/contribute', (route) => {
    route.fulfill({
      status: 202,
      body: JSON.stringify({
        contribution_id: 'contrib-123',
        status: 'PENDING',
        message: 'Contribución enviada',
      }),
    });
  });
}

export async function mockContributeOffError(page: Page, statusCode: number = 500) {
  await page.route('**/scan/contribute', (route) => {
    route.fulfill({
      status: statusCode,
      body: JSON.stringify({ detail: 'Error al contribuir' }),
    });
  });
}

export async function mockScanPhotoError(page: Page, statusCode: number = 422) {
  await page.route('**/scan/photo', (route) => {
    route.fulfill({
      status: statusCode,
      body: JSON.stringify({ detail: 'Error procesando foto' }),
    });
  });
}

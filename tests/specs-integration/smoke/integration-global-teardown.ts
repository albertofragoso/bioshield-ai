// tests/specs-integration/smoke/integration-global-teardown.ts
import { test } from '@playwright/test';
import { execSync } from 'child_process';

test('teardown: stop docker stack and remove volumes', async () => {
  execSync(
    'docker compose -f docker-compose.integration.yml down -v',
    { stdio: 'inherit', timeout: 60_000 },
  );
});

import { test, expect } from "@playwright/test";
import { readFileSync, readdirSync } from "fs";
import { join } from "path";

const FIXTURES_DIR = join(process.cwd(), "frontend/public/demo");
const REQUIRED_EVENT_TYPES = ["init", "ingredients", "done"];

test.describe("SSE trace fixtures — contract test", () => {
  const fixtures = readdirSync(FIXTURES_DIR).filter((f) => f.endsWith(".json"));

  test("3 fixtures exist", () => {
    expect(fixtures.length).toBeGreaterThanOrEqual(3);
  });

  for (const file of fixtures) {
    test(`fixture ${file} has correct schema`, () => {
      const raw = readFileSync(join(FIXTURES_DIR, file), "utf-8");
      const trace = JSON.parse(raw) as {
        barcode: string;
        product_name: string;
        events: Array<{ t_ms: number; type: string; data: object }>;
      };

      expect(trace).toHaveProperty("barcode");
      expect(trace).toHaveProperty("product_name");
      expect(Array.isArray(trace.events)).toBe(true);
      expect(trace.events.length).toBeGreaterThan(0);

      const types = trace.events.map((e) => e.type);
      for (const required of REQUIRED_EVENT_TYPES) {
        expect(types).toContain(required);
      }

      for (const event of trace.events) {
        expect(typeof event.t_ms).toBe("number");
        expect(typeof event.type).toBe("string");
        expect(typeof event.data).toBe("object");
      }
    });
  }
});

import path from "node:path";
import { fileURLToPath } from "node:url";

import { expect, test } from "@playwright/test";


const TEST_DIR = path.dirname(fileURLToPath(import.meta.url));
const HARNESS_PATH = path.join(
  TEST_DIR,
  "support",
  "extension_contract_harness.js",
);


async function loadHarness(page) {
  await page.setContent("<!doctype html><html><body></body></html>");
  await page.addScriptTag({ path: HARNESS_PATH });
}


test("preserves the uint64 maximum as an exact decimal string", async ({ page }) => {
  await loadHarness(page);

  const result = await page.evaluate(() => {
    const maximum = "18446744073709551615";
    const canonical = window.TPFrontendContract.canonicalUnsignedDecimal(
      maximum,
      maximum,
    );
    return JSON.parse(JSON.stringify({ seed: canonical })).seed;
  });

  expect(result).toBe("18446744073709551615");
});


test("rejects unsafe numeric seed transport", async ({ page }) => {
  await loadHarness(page);

  const result = await page.evaluate(() => {
    try {
      window.TPFrontendContract.canonicalUnsignedDecimal(
        18446744073709551615,
        "18446744073709551615",
      );
      return "accepted";
    } catch (error) {
      return error.message;
    }
  });

  expect(result).toContain("decimal string");
});


test("detects protected host method monkey patches", async ({ page }) => {
  await loadHarness(page);

  const result = await page.evaluate(() => {
    const host = {
      app: {
        queuePrompt() {},
        graphToPrompt() {},
      },
      nodePrototype: {
        onNodeCreated() {},
      },
      graphPrototype: {
        configure() {},
      },
    };
    const snapshot = window.TPFrontendContract.captureProtectedMethods(host);
    host.app.queuePrompt = function patchedQueuePrompt() {};

    try {
      window.TPFrontendContract.assertProtectedMethodsUnchanged(snapshot, host);
      return "accepted";
    } catch (error) {
      return error.message;
    }
  });

  expect(result).toContain("app.queuePrompt");
});


test("accepts an event-only extension that leaves host methods unchanged", async ({
  page,
}) => {
  await loadHarness(page);

  const result = await page.evaluate(() => {
    const host = {
      app: {
        queuePrompt() {},
        graphToPrompt() {},
      },
      nodePrototype: {
        onNodeCreated() {},
      },
      graphPrototype: {
        configure() {},
      },
    };
    const snapshot = window.TPFrontendContract.captureProtectedMethods(host);
    const listeners = new Map();
    host.addEventListener = (name, callback) => listeners.set(name, callback);
    host.addEventListener("synthetic-seed-event", () => {});
    window.TPFrontendContract.assertProtectedMethodsUnchanged(snapshot, host);
    return listeners.has("synthetic-seed-event");
  });

  expect(result).toBe(true);
});

// The cart item's `category` is the field the settlement budget gate checks against the Intent
// Mandate's `authorizedCategories`. It is also a field the two SDKs can disagree about silently:
// Pydantic gives it a default and emits it on every dump, while `JSON.stringify` drops an
// undefined key entirely. A cart built here without it would therefore canonicalize to different
// bytes than the same cart in Python, and every cross-SDK signature check would fail -- with a
// "bad signature" that says nothing about the real cause.
//
// So this pins the two things that keep the wire format identical: the sentinel spells the same
// in all three declarations, and the item shape the TypeScript builder signs matches the Python
// schema field for field.

import assert from "node:assert/strict";
import test from "node:test";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { AgentKeyManager } from "../src/agentKeyManager.js";
import { createSignedCartMandate } from "../src/agentMandateBuilder.js";
import { uncategorizedCartItemCategory } from "../src/sdkConstants.js";

const testDir = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(testDir, "..", "..", "..");
const engineSchemaPath = path.join(
  repoRoot, "packages", "mandateEngine", "mandates", "cartMandateSchema.py"
);
const pythonSdkModelsPath = path.join(
  repoRoot, "packages", "buyerSdkPy", "razoragent_buyer_sdk", "mandateModels.py"
);

const merchantSeed = "b".repeat(64);

function readSentinel(filePath: string): string | undefined {
  const declaration = fs
    .readFileSync(filePath, "utf-8")
    .split("\n")
    .find((line) => line.startsWith("uncategorizedCartItemCategory:"));
  return declaration?.split('"')[1];
}

// Field names declared on the Python CartItemSchema body, in declaration order.
function readPythonCartItemFields(filePath: string): readonly string[] {
  const lines = fs.readFileSync(filePath, "utf-8").split("\n");
  const start = lines.findIndex((line) => line.startsWith("class CartItemSchema"));
  assert.ok(start >= 0, `CartItemSchema not found in ${filePath}`);
  const fields: string[] = [];
  for (const line of lines.slice(start + 1)) {
    if (line.startsWith("class ")) {
      break;
    }
    const match = /^ {4}([a-zA-Z][a-zA-Z0-9]*): /.exec(line);
    if (match && match[1] !== "model_config") {
      fields.push(match[1]);
    }
  }
  return fields;
}

function buildOneItemCart(category?: string) {
  const merchantSigner = AgentKeyManager.fromSeed(merchantSeed);
  return createSignedCartMandate(
    {
      merchantGstin: "29AABCU9603R1ZJ",
      merchantStateCode: "29",
      buyerDeliveryPincode: "560001",
      buyerDeliveryStateCode: "29",
      items: [
        {
          skuId: "SKU-PARITY-01",
          quantity: 1,
          unitPricePaise: 100000,
          hsnCode: "8504",
          gstRatePercent: 18,
          lineTotalPaise: 100000,
          ...(category === undefined ? {} : { category })
        }
      ],
      taxableSubtotalPaise: 100000,
      taxBreakdown: { cgstPaise: 9000, sgstPaise: 9000, igstPaise: 0, totalTaxPaise: 18000 },
      totalPaise: 118000,
      inventoryLockToken: "lock_parity_01",
      inventoryLockExpiresAt: 2000000000
    },
    merchantSigner
  );
}

test("the uncategorized sentinel spells identically in all three declarations", () => {
  assert.equal(
    readSentinel(engineSchemaPath),
    uncategorizedCartItemCategory,
    "mandateEngine cartMandateSchema.py disagrees with sdkConstants.ts"
  );
  assert.equal(
    readSentinel(pythonSdkModelsPath),
    uncategorizedCartItemCategory,
    "razoragent_buyer_sdk mandateModels.py disagrees with sdkConstants.ts"
  );
});

test("a signed cart item always carries a category, even when the caller omits one", () => {
  const cart = buildOneItemCart();
  assert.equal(cart.items[0]?.category, uncategorizedCartItemCategory);
  // The signed bytes, not just the returned object: an item normalized after signing would
  // still read correctly here while verifying against different bytes.
  assert.ok(JSON.stringify(cart).includes(`"category":"${uncategorizedCartItemCategory}"`));
});

test("a caller-supplied category survives into the signed cart", () => {
  const cart = buildOneItemCart("industrial_electronics");
  assert.equal(cart.items[0]?.category, "industrial_electronics");
});

test("the signed item shape matches the Python CartItemSchema field for field", () => {
  const cart = buildOneItemCart("industrial_electronics");
  const signedFields = Object.keys(cart.items[0] ?? {}).sort();
  const pythonFields = [...readPythonCartItemFields(engineSchemaPath)].sort();
  assert.deepEqual(
    signedFields,
    pythonFields,
    "cart item fields diverged between the SDKs: canonical bytes will not match"
  );
});

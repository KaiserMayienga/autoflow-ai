import test from "node:test";
import assert from "node:assert/strict";
import { buildQuote } from "./quote.ts";

test("oil service quote is exact", () => {
  const q = buildQuote([{ sku: "OIL-5L", name: "Oil", qty: 1, unitCents: 3800 }, { sku: "OIL-FLT", name: "Filter", qty: 1, unitCents: 900 }], 0.7);
  assert.equal(q.partsCents, 4700);
  assert.equal(q.labourCents, 2100);
  assert.equal(q.vatCents, Math.round(6800 * 0.16));
  assert.equal(q.totalCents, 6800 + 1088);
});
test("no parts, labour only", () => {
  const q = buildQuote([], 0.8);
  assert.equal(q.totalCents, 2400 + Math.round(2400 * 0.16));
});

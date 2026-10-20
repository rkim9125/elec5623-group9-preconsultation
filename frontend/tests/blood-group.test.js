import test from "node:test";
import assert from "node:assert/strict";
import {
  bloodGroupLabel,
  parseBloodGroup,
  updateBloodGroup,
} from "../src/product/bloodGroup.js";
import { bodyProfileTranslationRows } from "../src/product/bodyProfileTranslations.js";

test("knowing only an ABO group never invents an Rh factor", () => {
  for (const abo of ["A", "B", "AB", "O"]) {
    assert.equal(updateBloodGroup("", "abo", abo), abo);
    assert.deepEqual(parseBloodGroup(abo), { abo, rh: "" });
    assert.equal(updateBloodGroup(abo, "rh", "+"), `${abo}+`);
    assert.equal(updateBloodGroup(`${abo}+`, "rh", ""), abo);
  }
});

test("existing ABO and Rh values reopen without data loss, unknown clears Rh", () => {
  assert.deepEqual(parseBloodGroup("AB-"), { abo: "AB", rh: "-" });
  assert.equal(updateBloodGroup("O+", "abo", "unknown"), "unknown");
  assert.equal(updateBloodGroup("unknown", "abo", "O"), "O");
  assert.equal(updateBloodGroup("AB-", "abo", ""), "");
  assert.equal(
    bloodGroupLabel("AB-", (s) => s),
    "AB-",
  );
  assert.equal(
    bloodGroupLabel("O", (s, p) => s.replace("{group}", p.group)),
    "O · Rh unknown",
  );
});

test("body/profile copy covers all five languages and preserves interpolation", () => {
  for (const row of bodyProfileTranslationRows) {
    assert.equal(row.length, 5);
    const params = (s) => [...s.matchAll(/\{(\w+)\}/g)].map((m) => m[1]).sort();
    for (const text of row) {
      assert.ok(text.trim());
      assert.deepEqual(params(text), params(row[0]));
    }
  }
});

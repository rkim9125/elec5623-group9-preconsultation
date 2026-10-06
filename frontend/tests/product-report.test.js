import test from "node:test";
import assert from "node:assert/strict";
import { shouldGenerateAssessment } from "../src/product/reportState.js";
import { reportPdf } from "../src/product/api.js";

const review = { status: "review", summary: { version: 1 } };

test("creating the review triggers assessment after the factual summary is ready", () => {
  assert.equal(shouldGenerateAssessment({ status: "active" }, review), true);
});

test("an intentional correction requires a new assessment, unchanged review does not", () => {
  assert.equal(
    shouldGenerateAssessment(review, { ...review, summary: { version: 2 } }),
    true,
  );
  assert.equal(
    shouldGenerateAssessment(review, { ...review, revision: 40 }),
    false,
  );
});

test("sharing, withdrawing and doctor review never automatically trigger generation", () => {
  assert.equal(
    shouldGenerateAssessment(review, { ...review, status: "approved" }),
    false,
  );
  assert.equal(
    shouldGenerateAssessment(review, { ...review, status: "withdrawn" }),
    false,
  );
  assert.equal(
    shouldGenerateAssessment({ status: "active" }, review, true),
    false,
  );
});

test("incomplete or unreconciled summaries cannot trigger assessment", () => {
  assert.equal(shouldGenerateAssessment({}, { status: "review" }), false);
  assert.equal(
    shouldGenerateAssessment(
      {},
      { ...review, summary: { version: 2, needs_reconciliation: true } },
    ),
    false,
  );
  assert.equal(
    shouldGenerateAssessment({}, { ...review, status: "interrupted" }),
    false,
  );
});

test("PDF download preserves authenticated same-origin access and encodes the record ID", async () => {
  const original = globalThis.fetch;
  globalThis.fetch = async (url, options) => {
    assert.equal(url, "/api/v1/intakes/record%2Fid/report.pdf");
    assert.equal(options.credentials, "same-origin");
    return new Response("%PDF-1.7 test", {
      headers: { "content-type": "application/pdf" },
    });
  };
  try {
    const result = await reportPdf("record/id");
    assert.equal(await result.text(), "%PDF-1.7 test");
  } finally {
    globalThis.fetch = original;
  }
});

test("PDF errors are shown rather than downloading an error document", async () => {
  const original = globalThis.fetch;
  globalThis.fetch = async () =>
    new Response(JSON.stringify({ detail: "An attachment is unavailable." }), {
      status: 409,
    });
  try {
    await assert.rejects(reportPdf("record"), /attachment is unavailable/);
    globalThis.fetch = async () =>
      new Response("<html>Sign in</html>", {
        headers: { "content-type": "text/html" },
      });
    await assert.rejects(reportPdf("record"), /did not return a PDF/);
  } finally {
    globalThis.fetch = original;
  }
});

import test from "node:test";
import assert from "node:assert/strict";
import {
  answerIsComplete,
  followupDraft,
  followupPayload,
} from "../src/product/followupModel.js";

const questions = [
  { id: "onset", options: [{ id: "A", value: "Today" }] },
  { id: "medicines", options: [] },
  { id: "activity", options: [] },
];

test("suggested answers are never selected without the patient's choice", () => {
  const draft = followupDraft({ questions });
  assert.equal(draft.onset.value, "");
  assert.equal(draft.onset.status, "MISSING");
  assert.equal(Object.values(draft).some(answerIsComplete), false);
});

test("saved draft restores edited free text and explicit uncertainty across reload", () => {
  const draft = followupDraft({
    questions,
    draft_answers: [
      { question_id: "onset", value: "Today, after lunch", status: "FILLED" },
      { question_id: "medicines", value: "", status: "UNCERTAIN" },
      {
        question_id: "old-question",
        value: "Not part of this set",
        status: "FILLED",
      },
    ],
  });
  assert.equal(draft.onset.value, "Today, after lunch");
  assert.equal(draft.medicines.status, "UNCERTAIN");
  assert.equal(draft.activity.status, "MISSING");
  assert.equal(draft["old-question"], undefined);
});

test("submission distinguishes an unanswered question from an explicit skip", () => {
  const draft = followupDraft({
    questions,
    draft_answers: [
      { question_id: "onset", value: "   ", status: "FILLED" },
      { question_id: "medicines", value: "outdated text", status: "SKIPPED" },
      {
        question_id: "activity",
        value: "  Walking is difficult  ",
        status: "FILLED",
      },
    ],
  });
  assert.deepEqual(followupPayload(questions, draft), [
    { question_id: "onset", value: "", status: "MISSING" },
    { question_id: "medicines", value: "", status: "SKIPPED" },
    {
      question_id: "activity",
      value: "Walking is difficult",
      status: "FILLED",
    },
  ]);
});

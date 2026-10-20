const ANSWER_STATUSES = new Set(["FILLED", "UNCERTAIN", "SKIPPED", "MISSING"]);

export function followupDraft(batch) {
  const saved = new Map(
    (batch.draft_answers || batch.answers || []).map((answer) => [
      answer.question_id,
      answer,
    ]),
  );
  return Object.fromEntries(
    (batch.questions || []).map((question) => {
      const answer = saved.get(question.id);
      return [
        question.id,
        {
          question_id: question.id,
          value: typeof answer?.value === "string" ? answer.value : "",
          status: ANSWER_STATUSES.has(answer?.status)
            ? answer.status
            : "MISSING",
        },
      ];
    }),
  );
}

export function answerIsComplete(answer) {
  return (
    answer?.status === "UNCERTAIN" ||
    answer?.status === "SKIPPED" ||
    (answer?.status === "FILLED" && !!answer.value?.trim())
  );
}

export function followupPayload(questions, answers) {
  return questions.map((question) => {
    const answer = answers[question.id];
    return {
      question_id: question.id,
      value: answer?.status === "FILLED" ? answer.value.trim() : "",
      status: answerIsComplete(answer) ? answer.status : "MISSING",
    };
  });
}

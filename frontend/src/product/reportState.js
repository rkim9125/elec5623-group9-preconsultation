// Called only after an intentional intake mutation, never after opening a page.
export function shouldGenerateAssessment(previous, next, doctor = false) {
  return Boolean(
    !doctor &&
    next?.status === "review" &&
    next.summary?.version &&
    !next.summary.needs_reconciliation &&
    (previous?.status !== "review" ||
      previous?.summary?.version !== next.summary.version),
  );
}

// Patient-facing names for the server's OLD CARTS dimensions. Clinical
// applicability and recorded statuses remain server-owned; no client scoring.
export const symptomDimensions = Object.freeze({
  O: {
    label: "When it started",
    icon: "clock",
    why: "An approximate time is fine. Tell us if it began suddenly or gradually.",
  },
  L: {
    label: "Where you feel it",
    icon: "person",
    why: "You can choose more than one area. Left and right refer to your own body.",
  },
  D: {
    label: "How long it lasts",
    icon: "clock",
    why: "Think about one episode, or tell us if the feeling is always there.",
  },
  C: {
    label: "What it feels like",
    icon: "message",
    why: "Everyday words are helpful. You do not need a medical term.",
  },
  A: {
    label: "What makes it worse",
    icon: "leg",
    why: "Think about activities, positions or situations. It is fine if you have not noticed a pattern.",
  },
  R: {
    label: "What helps",
    icon: "heart",
    why: "Tell us what you have tried and what changed, even if nothing helped.",
  },
  T: {
    label: "How it comes and goes",
    icon: "clock",
    why: "Tell us when it happens and whether it has changed over time.",
  },
  S: {
    label: "Intensity",
    icon: "heart",
    why: "Choose the intensity you feel. This is separate from how it affects your activities.",
  },
  radiation: {
    label: "Radiation or spread",
    icon: "arrow",
    why: "Tell us whether the feeling travels to another area.",
  },
});

export const symptomStatuses = Object.freeze({
  FILLED: { label: "Recorded", icon: "check" },
  PARTIAL: { label: "Some details recorded", icon: "file" },
  MISSING: { label: "Not yet recorded", icon: "file" },
  UNCERTAIN: { label: "You are not sure", icon: "info" },
  SKIPPED: { label: "You chose to skip", icon: "lock" },
  NOT_APPLICABLE: { label: "Not applicable", icon: "file" },
});

export function dimensionFor(field) {
  const id = field?.oldcarts_dimension;
  if (typeof id !== "string" || !Object.hasOwn(symptomDimensions, id))
    return null;
  const dimension = { id, ...symptomDimensions[id] };
  if (id === "D" && field.key === "symptom_duration")
    dimension.why =
      "Think about how long this problem has been present overall, from when it first started.";
  if (id === "O" && field.key === "symptom_onset")
    dimension.why =
      "An approximate date or time is fine. You can also say you are not sure.";
  return dimension;
}

function normalizedStatus(status) {
  return Object.hasOwn(symptomStatuses, status) ? status : "MISSING";
}

export function symptomStories(session) {
  if (!Array.isArray(session?.symptom_history)) return [];
  return session.symptom_history.flatMap((story) => {
    if (!story?.applicable || !story.concern_id) return [];
    const concern = session.concerns?.find(
      (item) => item.id === story.concern_id,
    );
    const rows = [
      ...(Array.isArray(story.dimensions) ? story.dimensions : []),
      ...(story.radiation?.applicable ? [story.radiation] : []),
    ];
    const dimensions = rows
      .filter(
        (item) =>
          Object.hasOwn(symptomDimensions, item.id) &&
          item.applicable !== false &&
          item.status !== "NOT_APPLICABLE",
      )
      .map((item) => ({
        ...symptomDimensions[item.id],
        id: item.id,
        status: normalizedStatus(item.status),
        keys: Array.isArray(item.keys)
          ? item.keys.filter((key) => typeof key === "string")
          : [],
        values: (Array.isArray(item.values) ? item.values : [])
          .filter((entry) => entry && entry.status !== "NOT_APPLICABLE")
          .map((entry) => ({
            key: entry.key,
            label:
              entry.key === "symptom_duration"
                ? "Overall duration"
                : entry.key === "symptom_episode_duration" ||
                    entry.key?.endsWith("episode_length")
                  ? "Episode duration"
                  : concern?.slots?.[entry.key]?.label,
            value: entry.value,
            status: normalizedStatus(entry.status),
          })),
        legacy: (Array.isArray(item.legacy_context)
          ? item.legacy_context
          : []
        ).filter((entry) => entry && entry.value),
      }));
    if (!dimensions.length) return [];
    return [
      {
        concern_id: story.concern_id,
        title: concern?.title || story.title || "Your concern",
        dimensions,
        // A count of unrecorded categories, never a health or safety score.
        unrecorded: dimensions.filter((item) =>
          ["MISSING", "PARTIAL"].includes(item.status),
        ).length,
      },
    ];
  });
}

export const painNumbers = Array.from({ length: 11 }, (_, number) => ({
  value: `${number}/10`,
  label: String(number),
}));
export function withPainOptions(options = [], presentation) {
  const base = Array.isArray(options) ? options : [];
  return presentation?.pain_scale === true ? [...base, ...painNumbers] : base;
}

export function selectPainNumber(selected, value) {
  const rest = selected.filter(
    (item) => !painNumbers.some((option) => option.value === item),
  );
  return selected.includes(value) ? rest : [...rest, value];
}

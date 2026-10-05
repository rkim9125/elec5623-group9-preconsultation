const CHOICES_HEADING = "Selected options:\n";
const DETAILS_HEADING = "\n\nAdditional details:\n";

// Values remain ordinary, readable patient answers at the API boundary. Only our
// exact, recognised format is parsed; existing prose is never inferred as a choice.
export function normalizeOptions(options = []) {
  if (!Array.isArray(options)) return [];
  const seen = new Set();
  return options
    .filter((option) => {
      if (
        !option ||
        typeof option.value !== "string" ||
        !option.value.trim() ||
        option.value.includes("\n") ||
        seen.has(option.value)
      )
        return false;
      seen.add(option.value);
      return true;
    })
    .map((option) => ({
      ...option,
      label:
        typeof option.label === "string" && option.label
          ? option.label
          : option.value,
    }));
}

export function parseGuidedAnswer(value = "", options = []) {
  const original = typeof value === "string" ? value : "";
  const fallback = { selected: [], details: original, structured: false };
  if (!original.startsWith(CHOICES_HEADING)) return fallback;
  const detailAt = original.indexOf(DETAILS_HEADING, CHOICES_HEADING.length);
  const choices = original.slice(
    CHOICES_HEADING.length,
    detailAt < 0 ? undefined : detailAt,
  );
  const known = new Set(
    normalizeOptions(options).map((option) => option.value),
  );
  const lines = choices.split("\n");
  if (
    !lines.length ||
    lines.some((line) => !line.startsWith("- ") || !known.has(line.slice(2)))
  )
    return fallback;
  const selected = lines.map((line) => line.slice(2));
  if (new Set(selected).size !== selected.length) return fallback;
  return {
    selected,
    details:
      detailAt < 0 ? "" : original.slice(detailAt + DETAILS_HEADING.length),
    structured: true,
  };
}

export function serializeGuidedAnswer({ selected = [], details = "" }) {
  const unique = [...new Set(selected)];
  if (!unique.length) return details;
  return `${CHOICES_HEADING}${unique.map((value) => `- ${value}`).join("\n")}${details ? `${DETAILS_HEADING}${details}` : ""}`;
}

export function toggleGuidedSelection(selected, value, multiple = true) {
  if (selected.includes(value))
    return selected.filter((item) => item !== value);
  return multiple ? [...selected, value] : [value];
}

export function appendGuidedDetails(value, text, options = []) {
  const parsed = parseGuidedAnswer(value, options);
  return serializeGuidedAnswer({
    selected: parsed.selected,
    details: parsed.details ? `${parsed.details}\n\n${text}` : text,
  });
}

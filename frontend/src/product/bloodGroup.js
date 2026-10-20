// Keep the existing API value (O+, AB-, …); an ABO-only value deliberately
// carries no Rh information. Never infer a positive or negative Rh factor.
export function parseBloodGroup(value = "") {
  if (value === "unknown") return { abo: "unknown", rh: "" };
  const match = /^(AB|A|B|O)([+-]?)$/.exec(value);
  return match ? { abo: match[1], rh: match[2] } : { abo: "", rh: "" };
}

export function updateBloodGroup(value, part, next) {
  const current = parseBloodGroup(value);
  const abo = part === "abo" ? next : current.abo;
  if (!abo || abo === "unknown") return abo;
  const rh = part === "rh" ? next : current.rh;
  return `${abo}${rh === "+" || rh === "-" ? rh : ""}`;
}

export function bloodGroupLabel(value, t) {
  const { abo, rh } = parseBloodGroup(value);
  if (!abo) return "";
  if (abo === "unknown") return t("I don’t know");
  return rh ? `${abo}${rh}` : t("{group} · Rh unknown", { group: abo });
}

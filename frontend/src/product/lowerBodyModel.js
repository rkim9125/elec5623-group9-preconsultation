// English copy is kept separate for the product's future translation resources.
export const bodyMapCopy = {
  title: "Body map",
  description: "Select the area you’d like to record.",
  viewLabel: "Body view",
  front: "Front",
  back: "Back",
  guide: "Tap an area",
  note: "Left and right refer to your body.",
  list: "Or select from the list",
  selected: "SELECTED AREA",
  empty: "No area selected",
  clear: "Clear",
};
// These are diagram segment identifiers, not medical codes.
export const lowerBodyShapes = [
  { key: "thigh", name: "Thigh", x: 52, y: 65, w: 49, h: 96 },
  { key: "knee", name: "Knee", x: 59, y: 170, w: 44, h: 44 },
  { key: "shin", name: "Shin", x: 56, y: 223, w: 44, h: 65 },
  { key: "ankle", name: "Ankle", x: 53, y: 291, w: 44, h: 30 },
  { key: "foot", name: "Foot", x: 40, y: 323, w: 53, h: 28 },
];
export function areaName(key, view) {
  if (view === "back" && key === "shin") return "Calf";
  if (view === "back" && key === "knee") return "Back of knee";
  return lowerBodyShapes.find((shape) => shape.key === key)?.name || "";
}
export const areaSummary = ({ side, key, view }) =>
  `${side} ${areaName(key, view).toLowerCase()} · ${bodyMapCopy[view]}`;
// The existing form stores readable answers. Preserve the diagram view explicitly.
export const lowerBodyOptions = ["front", "back"].flatMap((view) =>
  lowerBodyShapes.flatMap(({ key }) =>
    ["Right", "Left"].map((side) => {
      const area = { side, key, view };
      return { value: areaSummary(area), label: areaSummary(area), area };
    }),
  ),
);
export const areaFromAnswer = (selected) =>
  lowerBodyOptions.find((option) => option.value === selected[0])?.area || null;

export const bodyOptionsFor = (presentation) =>
  presentation?.kind === "body_map" && presentation.illustration === "legs"
    ? [...lowerBodyOptions, ...(presentation.options || [])]
    : presentation?.options;

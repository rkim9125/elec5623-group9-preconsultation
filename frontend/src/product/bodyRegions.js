const box = (x, y, width, height, rx = 10) => ({ x, y, width, height, rx });

// Front-facing figures place the patient's left on the viewer's right.
const regions = {
  legs: {
    left_thigh: box(155, 92, 43, 77, 16),
    right_thigh: box(102, 92, 43, 77, 16),
    left_knee: box(157, 174, 38, 32, 14),
    right_knee: box(105, 174, 38, 32, 14),
    left_calf: box(155, 211, 36, 64, 14),
    right_calf: box(109, 211, 36, 64, 14),
    left_shin: box(155, 211, 36, 64, 14),
    right_shin: box(109, 211, 36, 64, 14),
    left_ankle: box(158, 279, 29, 26, 8),
    right_ankle: box(113, 279, 29, 26, 8),
    left_foot: box(157, 310, 44, 26, 9),
    right_foot: box(99, 310, 44, 26, 9),
  },
  back: {
    lower_back_left: box(98, 180, 34, 55),
    lower_back_centre: box(137, 180, 26, 55),
    lower_back_right: box(168, 180, 34, 55),
  },
  neck_shoulders: {
    neck: box(131, 116, 38, 45),
    left_shoulder: box(66, 149, 60, 42, 16),
    right_shoulder: box(174, 149, 60, 42, 16),
  },
  arms_hands: {
    left_upper_arm: box(197, 107, 27, 54),
    right_upper_arm: box(76, 107, 27, 54),
    left_elbow: box(207, 166, 30, 29),
    right_elbow: box(63, 166, 30, 29),
    left_forearm: box(216, 200, 27, 57),
    right_forearm: box(57, 200, 27, 57),
    left_wrist: box(224, 262, 28, 23, 7),
    right_wrist: box(48, 262, 28, 23, 7),
    left_hand: box(231, 290, 35, 45, 13),
    right_hand: box(34, 290, 35, 45, 13),
  },
  head: {
    forehead: box(115, 119, 70, 32),
    left_temple: box(183, 151, 26, 49),
    right_temple: box(91, 151, 26, 49),
    top_head: box(113, 76, 74, 32, 16),
    back_head: box(107, 120, 86, 108, 32),
  },
  abdomen: {
    upper_abdomen_left: box(173, 134, 41, 48),
    upper_abdomen_centre: box(128, 134, 41, 48),
    upper_abdomen_right: box(83, 134, 41, 48),
    middle_abdomen_left: box(173, 188, 41, 48),
    around_navel: box(128, 188, 41, 48),
    middle_abdomen_right: box(83, 188, 41, 48),
    lower_abdomen_left: box(173, 242, 41, 48),
    lower_abdomen_centre: box(128, 242, 41, 48),
    lower_abdomen_right: box(83, 242, 41, 48),
  },
  body: {
    face: box(135, 41, 30, 29),
    scalp: box(129, 17, 42, 20),
    neck: box(139, 74, 22, 20, 6),
    chest: box(117, 100, 66, 40),
    back: box(117, 100, 66, 98),
    abdomen: box(121, 145, 58, 47),
    left_arm: box(195, 112, 25, 84),
    right_arm: box(80, 112, 25, 84),
    left_hand: box(210, 204, 29, 33),
    right_hand: box(61, 204, 29, 33),
    left_leg: box(153, 221, 33, 93),
    right_leg: box(114, 221, 33, 93),
    left_foot: box(153, 321, 42, 22),
    right_foot: box(105, 321, 42, 22),
  },
};

export function bodyMapViews(illustration) {
  if (["back", "neck_shoulders"].includes(illustration)) return ["back"];
  if (["legs", "head", "body"].includes(illustration)) return ["front", "back"];
  return ["front"];
}

export function getBodyRegion(illustration, region, view = "front") {
  const shape = regions[illustration]?.[region];
  if (!shape) return null;
  if (
    illustration === "legs" &&
    ((region.includes("calf") && view === "front") ||
      ((region.includes("knee") || region.includes("shin")) && view === "back"))
  )
    return null;
  if (
    illustration === "head" &&
    (region === "back_head") !== (view === "back") &&
    region !== "top_head"
  )
    return null;
  if (
    illustration === "body" &&
    ((region === "back" && view === "front") ||
      (["face", "chest", "abdomen"].includes(region) && view === "back"))
  )
    return null;
  const alreadyRear = ["back", "neck_shoulders"].includes(illustration);
  if (view === "back" && !alreadyRear)
    return { ...shape, x: 300 - shape.x - shape.width };
  return { ...shape };
}

import React, { useState } from "react";
import { createRoot } from "react-dom/client";
import LowerBodyMap from "../../../src/product/LowerBodyMap.jsx";
import GuidedField from "../../../src/product/GuidedField.jsx";
import "../../../src/product/product.css";
function Harness() {
  const [value, setValue] = useState(null);
  const [answer, setAnswer] = useState("");
  if (location.search.includes("guided"))
    return (
      <GuidedField
        field={{
          key: "leg.pain_site",
          presentation: {
            kind: "body_map",
            illustration: "legs",
            options: [{ value: "Right knee", label: "Right knee" }],
          },
        }}
        answer={{ value: answer }}
        inputId="body"
        onChange={setAnswer}
      />
    );
  if (location.search.includes("initial"))
    return (
      <LowerBodyMap
        initialValue={{ side: "Left", key: "shin", view: "back" }}
      />
    );
  return <LowerBodyMap value={value} onChange={setValue} />;
}
createRoot(document.getElementById("root")).render(<Harness />);

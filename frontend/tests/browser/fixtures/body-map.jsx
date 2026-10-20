import React, { useState } from "react";
import { createRoot } from "react-dom/client";
import LowerBodyMap from "../../../src/product/LowerBodyMap.jsx";
import GuidedField from "../../../src/product/GuidedField.jsx";
import ProfileWizard from "../../../src/product/ProfileWizard.jsx";
import { LocaleProvider } from "../../../src/product/i18n.jsx";
import "../../../src/product/product.css";
import "../../../src/product/wizard.css";
function Harness() {
  const [value, setValue] = useState(null);
  const [answer, setAnswer] = useState(
    location.search.includes("legacy")
      ? "Selected options:\n- Right knee\n\nAdditional details:\nPatient’s original detail."
      : "",
  );
  const [saved, setSaved] = useState(null);
  if (location.search.includes("profile"))
    return saved ? (
      <output>{JSON.stringify(saved)}</output>
    ) : (
      <ProfileWizard onClose={() => {}} onSaved={setSaved} />
    );
  if (location.search.includes("guided"))
    return (
      <>
        <GuidedField
          field={{
            key: "leg.pain_site",
            presentation: {
              kind: "body_map",
              illustration: "legs",
              multiple: false,
              options: [{ value: "Right knee", label: "Right knee" }],
            },
          }}
          answer={{ value: answer }}
          inputId="body"
          onChange={setAnswer}
        />
        <output data-testid="saved-answer">{answer}</output>
      </>
    );
  if (location.search.includes("initial"))
    return (
      <LowerBodyMap
        initialValue={{ side: "Left", key: "shin", view: "back" }}
      />
    );
  return <LowerBodyMap value={value} onChange={setValue} />;
}
createRoot(document.getElementById("root")).render(
  <LocaleProvider>
    <Harness />
  </LocaleProvider>,
);

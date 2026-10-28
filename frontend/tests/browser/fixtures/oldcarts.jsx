import React, { useState } from "react";
import { createRoot } from "react-dom/client";
import { BaselineForm } from "../../../src/product/Preparation.jsx";
import { LocaleProvider } from "../../../src/product/i18n.jsx";
import "../../../src/product/product.css";
import "../../../src/product/wizard.css";

function Fixture() {
  const [session, setSession] = useState({
    id: "story-test",
    revision: 1,
    status: "active",
    concerns: [{ id: "leg", title: "Leg pain", workflow_id: "WF-01" }],
  });
  return (
    <LocaleProvider>
      <main>
        <BaselineForm
          session={session}
          onUpdate={setSession}
          refresh={() => {}}
          Attachments={() => <div />}
        />
      </main>
    </LocaleProvider>
  );
}
createRoot(document.getElementById("root")).render(<Fixture />);

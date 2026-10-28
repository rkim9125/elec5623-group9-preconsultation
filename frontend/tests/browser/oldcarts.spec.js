import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

test("description is saved before organization; extracted details are skipped and remain editable", async ({
  page,
}) => {
  let revision = 1;
  let organized = false;
  let answers = {};
  const calls = [];
  const fields = () =>
    [
      {
        key: "concern_description",
        label: "Your description",
        question: "Tell us about your leg pain.",
        status: answers.concern_description ? "FILLED" : "MISSING",
        value: answers.concern_description || "",
      },
      {
        key: "symptom_onset",
        label: "Onset",
        question: "When did it start?",
        oldcarts_dimension: "O",
        status: organized ? "FILLED" : "MISSING",
        value: organized ? "Three days ago" : "",
      },
      {
        key: "severity",
        label: "Intensity",
        question: "How intense is it?",
        oldcarts_dimension: "S",
        status: "MISSING",
        presentation: {
          kind: "choices",
          multiple: false,
          pain_scale: true,
          options: [
            { label: "Mild", value: "Mild" },
            { label: "Moderate", value: "Moderate" },
            { label: "Severe", value: "Severe" },
          ],
        },
      },
    ].map((field) => ({ ...field, concern_id: "leg" }));
  const session = () => ({
    id: "story-test",
    revision,
    status: "active",
    ai_status: { mode: "live" },
    concerns: [{ id: "leg", title: "Leg pain", workflow_id: "WF-01" }],
    symptom_history: [
      {
        concern_id: "leg",
        applicable: true,
        dimensions: [
          {
            id: "O",
            status: organized ? "FILLED" : "MISSING",
            keys: ["symptom_onset"],
            values: organized
              ? [
                  {
                    key: "symptom_onset",
                    value: "Three days ago",
                    status: "FILLED",
                  },
                ]
              : [],
          },
          { id: "S", status: "MISSING", keys: ["severity"], values: [] },
        ],
      },
    ],
  });
  await page.route("**/api/v1/intakes/story-test/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith("/form"))
      return route.fulfill({
        json: {
          revision,
          groups: [
            {
              id: "leg",
              workflow_id: "WF-01",
              title: "Leg pain",
              fields: fields(),
            },
          ],
        },
      });
    if (path.endsWith("/baseline")) {
      calls.push("save");
      const body = route.request().postDataJSON();
      expect(body.revision).toBe(revision);
      answers = Object.fromEntries(
        body.answers.map((answer) => [answer.key, answer.value]),
      );
      revision++;
      return route.fulfill({ json: session() });
    }
    if (path.endsWith("/organize")) {
      calls.push("organize");
      expect(answers.concern_description).toBe(
        "My knee started hurting three days ago.",
      );
      expect(route.request().postDataJSON().revision).toBe(revision);
      organized = true;
      revision++;
      return route.fulfill({ json: session() });
    }
    return route.abort();
  });
  await page.goto("/tests/browser/fixtures/oldcarts.html");
  await page
    .locator("textarea")
    .fill("My knee started hurting three days ago.");
  await page.getByRole("button", { name: "Continue", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "How intense is it?" }),
  ).toBeVisible();
  expect(calls.slice(0, 2)).toEqual(["save", "organize"]);
  await expect(
    page.getByText(
      "We’ve filled in details from your description. You can check or change them at any time.",
    ),
  ).toBeVisible();
  await page.getByRole("button", { name: "Mild", exact: true }).click();
  await page
    .getByRole("button", { name: "Add a pain number (optional)" })
    .click();
  await page
    .getByRole("button", { name: "Pain level 3 out of 10", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Mild", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
  await page
    .locator(".wizard-actions")
    .getByRole("button", { name: "Review answers", exact: true })
    .last()
    .click();
  await page.getByTestId("symptom-story").locator("summary").click();
  await expect(page.getByTestId("symptom-story")).toContainText(
    "Three days ago",
  );
  await page
    .getByRole("button", {
      name: "Edit When it started for Leg pain",
      exact: true,
    })
    .click();
  await expect(
    page.getByRole("heading", { name: "When did it start?" }),
  ).toBeVisible();
  await expect(page.locator("textarea")).toHaveValue("Three days ago");
  await page.setViewportSize({ width: 360, height: 800 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await expect(page.locator(".wizard-question-card")).toHaveCSS("opacity", "1");
  const scan = await new AxeBuilder({ page }).analyze();
  expect(
    scan.violations.filter((item) =>
      ["critical", "serious"].includes(item.impact),
    ),
  ).toEqual([]);
});

for (const failReload of [false, true]) {
  test(`organization preserves sensitive permission and ${failReload ? "blocks stale edits after reload failure" : "keeps uncertainty when adding details"}`, async ({
    page,
  }) => {
    let organized = false;
    let failed = false;
    let revision = 1;
    let saved = [];
    const snapshot = () => ({
      id: "story-test",
      revision,
      status: "active",
      ai_status: { mode: "live" },
      concerns: [
        { id: "leg", title: "Menstrual symptoms", workflow_id: "WF-19" },
      ],
    });
    await page.route("**/api/v1/intakes/story-test/**", async (route) => {
      const path = new URL(route.request().url()).pathname;
      if (path.endsWith("/form")) {
        if (organized && failReload && !failed) {
          failed = true;
          return route.fulfill({
            status: 503,
            json: { detail: "Reload is temporarily unavailable." },
          });
        }
        return route.fulfill({
          json: {
            revision,
            groups: [
              {
                id: "leg",
                title: "Menstrual symptoms",
                workflow_id: "WF-19",
                fields: [
                  {
                    key: "sensitive_permission",
                    input_type: "permission",
                    status: "FILLED",
                    value: "Yes",
                    label: "Permission",
                  },
                  {
                    key: "concern_description",
                    requires_permission: true,
                    label: "Your description",
                    question: "Tell us about this concern.",
                    status: organized ? "FILLED" : "MISSING",
                    value: organized ? "A new symptom" : "",
                  },
                  {
                    key: "symptom_onset",
                    requires_permission: true,
                    oldcarts_dimension: "O",
                    label: "Onset",
                    question: "When did you first notice it?",
                    status: organized ? "FILLED" : "MISSING",
                    value: organized ? "Three days ago" : "",
                  },
                  {
                    key: "symptom_duration",
                    requires_permission: true,
                    oldcarts_dimension: "D",
                    label: "Overall duration",
                    question: "How long has this symptom been present?",
                    status: "MISSING",
                    value: "",
                  },
                ].map((field) => ({ ...field, concern_id: "leg" })),
              },
            ],
          },
        });
      }
      if (path.endsWith("/baseline")) {
        saved = route.request().postDataJSON().answers;
        revision++;
        return route.fulfill({ json: snapshot() });
      }
      if (path.endsWith("/organize")) {
        organized = true;
        revision++;
        return route.fulfill({ json: snapshot() });
      }
      return route.abort();
    });
    await page.goto("/tests/browser/fixtures/oldcarts.html");
    await expect(
      page.getByRole("heading", { name: "Tell us about this concern." }),
    ).toBeVisible();
    await page.locator("textarea").fill("A new symptom");
    await page.getByRole("button", { name: "Continue", exact: true }).click();
    if (failReload) {
      await expect(
        page.getByRole("button", { name: "Retry loading questions" }),
      ).toBeVisible();
      await expect(page.locator("textarea")).toHaveCount(0);
      await page
        .getByRole("button", { name: "Retry loading questions" })
        .click();
    }
    await expect(
      page.getByRole("heading", {
        name: "How long has this symptom been present?",
      }),
    ).toBeVisible();
    await page
      .getByRole("button", { name: "I’m not sure", exact: true })
      .click();
    await page.locator("textarea").fill("Maybe about a week");
    await expect(
      page.getByRole("button", { name: "I’m not sure", exact: true }),
    ).toHaveAttribute("aria-pressed", "true");
    await expect
      .poll(() => saved.find((item) => item.key === "symptom_duration")?.value)
      .toBe("Maybe about a week");
    expect(saved.find((item) => item.key === "symptom_duration").status).toBe(
      "UNCERTAIN",
    );
    expect(saved.find((item) => item.key === "symptom_onset").value).toBe(
      "Three days ago",
    );
    await page.locator(".wizard-actions").getByRole("button", { name: "Review answers", exact: true }).last().click();
    await expect(page.locator(".wizard-review-list")).toContainText("I’m not sure — Maybe about a week");
    await expect(page.getByRole("heading", { name: "The essentials, in your own words." })).toBeFocused();
  });
}

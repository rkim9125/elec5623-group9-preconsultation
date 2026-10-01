import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { initial, KEY } from "../../src/model.js";
import { seedDatabase, ACCOUNT_KEY } from "../../src/account/domain.js";
const data = () => {
  const d = initial();
  d.reasons = ["Demo visit"];
  for (const key of [
    "onset",
    "course",
    "severity",
    "impact",
    "medicines",
    "allergies",
    "questions",
  ])
    d[key].status = "unknown";
  return d;
};
const next = (page) => page.getByRole("button", { name: /^Continue/ }).click();
const stored = (page) =>
  page.evaluate((key) => JSON.parse(sessionStorage.getItem(key)), KEY);
async function seed(page, d) {
  await page.addInitScript(
    ({ key, d }) => {
      if (!sessionStorage.getItem(key))
        sessionStorage.setItem(key, JSON.stringify(d));
      window.answerWrites = 0;
      const original = Storage.prototype.setItem;
      Storage.prototype.setItem = function (k, v) {
        if (k !== "visit-notes-language") window.answerWrites++;
        return original.call(this, k, v);
      };
    },
    { key: KEY, d },
  );
  await page.goto("/#history");
}
for (const width of [360, 1440])
  test(`history tags keyboard, language, restore and review ${width}`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 1000 });
    await seed(page, data());
    const diabetes = page.getByRole("checkbox", {
      name: "Diabetes",
      exact: true,
    });
    await diabetes.focus();
    await page.keyboard.press("Space");
    await expect(diabetes).toBeChecked();
    await page.keyboard.press("Space");
    await expect(diabetes).not.toBeChecked();
    await expect
      .poll(async () => (await stored(page)).history.status)
      .toBe("unanswered");
    await diabetes.check();
    await page
      .getByRole("checkbox", { name: "Previous surgery", exact: true })
      .check();
    await page
      .getByLabel("Additional history or details")
      .fill("Original explanation 원문");
    const before = await stored(page),
      writes = await page.evaluate(() => window.answerWrites);
    await page.locator("#ui-language").selectOption("ko");
    await expect(
      page.getByRole("checkbox", { name: "당뇨병", exact: true }),
    ).toBeChecked();
    await expect(page.getByLabel("추가 병력 또는 설명")).toHaveValue(
      "Original explanation 원문",
    );
    expect(await stored(page)).toEqual(before);
    expect(await page.evaluate(() => window.answerWrites)).toBe(writes);
    await expect(page).toHaveURL(/#history$/);
    expect(
      (
        await new AxeBuilder({ page })
          .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
          .analyze()
      ).violations,
    ).toEqual([]);
    await page.screenshot({
      path: `test-results/screenshots/history-${width}-ko.png`,
      fullPage: true,
    });
    await page.locator("#ui-language").selectOption("en");
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    for (const label of await page.locator(".history-tag").all()) {
      const box = await label.boundingBox();
      expect(box.height).toBeGreaterThanOrEqual(44);
      expect(box.width).toBeGreaterThanOrEqual(44);
    }
    await page.screenshot({
      path: `test-results/screenshots/history-${width}-en.png`,
      fullPage: true,
    });
    await next(page);
    await page.goBack();
    await expect(diabetes).toBeChecked();
    await page.reload();
    await expect(diabetes).toBeChecked();
    await expect(page.getByLabel("Additional history or details")).toHaveValue(
      "Original explanation 원문",
    );
    for (let i = 0; i < 4; i++) await next(page);
    const section = page.locator(".summary section").filter({
      has: page.getByRole("heading", {
        name: "Medical history",
        exact: true,
      }),
    });
    await expect(section).toContainText("Diabetes");
    await expect(section).toContainText("Previous surgery");
    await expect(section).toContainText("Original explanation 원문");
    await page.locator(".approval input").check();
    await section.getByRole("button").click();
    await diabetes.uncheck();
    await page.locator(".actions .primary").click();
    await expect(page.locator(".approval input")).not.toBeChecked();
    await expect(section).not.toContainText("Diabetes");
  });
test("exclusive responses retain legacy input; empty remains unanswered", async ({
  page,
}) => {
  const d = data();
  d.history = { status: "answered", value: "Legacy free text" };
  await seed(page, d);
  await expect(page.getByLabel("Additional history or details")).toHaveValue(
    "Legacy free text",
  );
  await page.getByRole("checkbox", { name: "Asthma", exact: true }).check();
  for (const [name, status] of [
    ["None", "none"],
    ["Not sure", "unknown"],
    ["Prefer not to answer", "declined"],
  ]) {
    await page.getByRole("button", { name, exact: true }).click();
    await expect(
      page.getByRole("checkbox", { name: "Asthma", exact: true }),
    ).not.toBeChecked();
    await expect(
      page.getByLabel("Additional history or details"),
    ).toBeDisabled();
    expect((await stored(page)).history).toEqual({
      status,
      value: "Legacy free text",
      tags: ["asthma"],
    });
    for (let i = 0; i < 4; i++) await next(page);
    await expect(page.locator(".summary")).not.toContainText(
      "Legacy free text",
    );
    await expect(page.locator(".summary")).not.toContainText("Asthma");
    await page
      .getByRole("button", { name: "Edit Medical history", exact: true })
      .click();
    await page
      .getByRole("button", { name: "Edit history selections and text" })
      .click();
    await expect(
      page.getByRole("checkbox", { name: "Asthma", exact: true }),
    ).toBeChecked();
    await expect(page.getByLabel("Additional history or details")).toHaveValue(
      "Legacy free text",
    );
    await page.goto("/#history");
  }
  await page.getByRole("checkbox", { name: "Asthma", exact: true }).uncheck();
  await page.getByLabel("Additional history or details").fill("");
  await next(page);
  expect((await stored(page)).history.status).toBe("unanswered");
});
test("tag-only and text-only answers both advance", async ({ page }) => {
  await seed(page, data());
  await page.getByRole("checkbox", { name: "Diabetes", exact: true }).check();
  await next(page);
  await expect(page).toHaveURL(/#medicines$/);
  await page.goBack();
  await page.getByRole("checkbox", { name: "Diabetes", exact: true }).uncheck();
  await page.getByLabel("Additional history or details").fill("Text only");
  await next(page);
  await expect(page).toHaveURL(/#medicines$/);
});
test("account resume, immutable handoff and doctor summary/originals", async ({
  page,
}) => {
  const db = seedDatabase();
  const record = db.intakes.find((i) => i.id === "intake-a-draft");
  record.data = data();
  record.step = "history";
  await page.addInitScript(
    ({ key, db }) => {
      if (!sessionStorage.getItem(key))
        sessionStorage.setItem(key, JSON.stringify(db));
    },
    { key: ACCOUNT_KEY, db },
  );
  await page.goto("/#/intakes/intake-a-draft/edit/history");
  await page.locator("#email").fill("garam@example.test");
  await page.locator("#password").fill("Demo1234!");
  await page.getByRole("button", { name: "Log in", exact: true }).click();
  await page
    .getByRole("checkbox", { name: "Kidney disease", exact: true })
    .check();
  await page
    .getByLabel("Additional history or details")
    .fill("Original patient detail");
  await page.getByRole("button", { name: /Save and go to my notes/ }).click();
  await page.goto("/#/intakes/intake-a-draft/edit/history");
  await expect(
    page.getByRole("checkbox", { name: "Kidney disease", exact: true }),
  ).toBeChecked();
  await page.reload();
  await expect(page.getByLabel("Additional history or details")).toHaveValue(
    "Original patient detail",
  );
  for (let i = 0; i < 4; i++) await next(page);
  await page.locator(".approval input").check();
  await page
    .getByRole("button", { name: /Confirm and simulate handoff/ })
    .click();
  await expect
    .poll(() =>
      page.evaluate(
        (key) =>
          JSON.parse(sessionStorage.getItem(key)).intakes.find(
            (i) => i.id === "intake-a-draft",
          ).status,
        ACCOUNT_KEY,
      ),
    )
    .toBe("sent");
  const snapshot = await page.evaluate(
    (key) =>
      JSON.parse(sessionStorage.getItem(key)).intakes.find(
        (i) => i.id === "intake-a-draft",
      ).snapshot,
    ACCOUNT_KEY,
  );
  await page.goto("/#/intakes/intake-a-draft/edit/history");
  await expect(page).toHaveURL(/#\/intakes\/intake-a-draft$/);
  await expect(page.locator(".history-input")).toHaveCount(0);
  await page.getByRole("button", { name: "Log out", exact: true }).click();
  await page.getByRole("button", { name: /Demo doctor/ }).click();
  await page.getByRole("button", { name: "Log in", exact: true }).click();
  await expect(page).toHaveURL(/#\/doctor$/);
  await page.goto("/#/doctor/appointments/apt-a-next");
  await expect(page.locator(".doctor-summary")).toContainText("Kidney disease");
  await expect(page.locator(".doctor-summary")).toContainText(
    "Original patient detail",
  );
  await page
    .getByRole("button", { name: "Show all original answers", exact: true })
    .click();
  await expect(page.locator(".doctor-original")).toContainText(
    "Kidney disease",
  );
  await expect(page.locator(".doctor-original")).toContainText(
    "Original patient detail",
  );
  await page.locator("#ui-language").selectOption("ko");
  await expect(page.locator(".doctor-original")).toContainText("신장질환");
  await expect(page.locator(".doctor-original")).toContainText(
    "Original patient detail",
  );
  expect(
    await page.evaluate(
      (key) =>
        JSON.parse(sessionStorage.getItem(key)).intakes.find(
          (i) => i.id === "intake-a-draft",
        ).snapshot,
      ACCOUNT_KEY,
    ),
  ).toEqual(snapshot);
});

test("legacy empty answered response has a localized, linked and focused error", async ({
  page,
}) => {
  const d = data();
  d.history = { status: "answered", value: "" };
  await seed(page, d);
  await next(page);
  await expect(page.getByRole("alert")).toContainText("Select a history tag");
  await expect(page.locator("#free-answer")).toBeFocused();
  await expect(page.locator("#free-answer")).toHaveAttribute(
    "aria-describedby",
    "form-error",
  );
  await page.locator("#ui-language").selectOption("ko");
  await expect(page.getByRole("alert")).toContainText("병력 태그");
});

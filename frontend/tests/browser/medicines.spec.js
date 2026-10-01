import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { initial, KEY } from "../../src/model.js";
const read = (page) =>
  page.evaluate((key) => JSON.parse(sessionStorage.getItem(key)), KEY);
const next = (page) => page.getByRole("button", { name: /^Continue/ }).click();
async function setup(page, medicines) {
  const d = initial();
  d.reasons = ["Demo visit"];
  for (const key of [
    "onset",
    "course",
    "severity",
    "impact",
    "history",
    "allergies",
    "questions",
  ])
    d[key].status = "unknown";
  if (medicines) d.medicines = medicines;
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
  await page.goto("/#medicines");
}
for (const width of [360, 1440])
  test(`medicine tags, keyboard, languages, persistence and summary ${width}`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 1000 });
    await setup(page);
    const pain = page.getByRole("checkbox", {
      name: "Pain relief",
      exact: true,
    });
    await pain.focus();
    await page.keyboard.press("Space");
    await expect(pain).toBeChecked();
    await page
      .getByRole("checkbox", { name: "Blood pressure medication", exact: true })
      .check();
    expect((await read(page)).medicines.items).toEqual([]);
    await page.getByRole("button", { name: /Add Medicines/ }).click();
    await page.getByLabel("Medicine name").fill("My original medicine");
    await page
      .getByLabel("Dose and how you take it")
      .fill("Original dose and frequency");
    await pain.uncheck();
    expect((await read(page)).medicines.items[0].name).toBe(
      "My original medicine",
    );
    await pain.check();
    const before = await read(page),
      writes = await page.evaluate(() => window.answerWrites);
    await page.locator("#ui-language").selectOption("ko");
    await expect(
      page.getByRole("checkbox", { name: "진통제", exact: true }),
    ).toBeChecked();
    expect(await read(page)).toEqual(before);
    expect(await page.evaluate(() => window.answerWrites)).toBe(writes);
    await expect(page).toHaveURL(/#medicines$/);
    await page.screenshot({
      path: `test-results/screenshots/medicines-${width}-ko.png`,
      fullPage: true,
    });
    await page.locator("#ui-language").selectOption("en");
    expect(
      (
        await new AxeBuilder({ page })
          .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
          .analyze()
      ).violations,
    ).toEqual([]);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    for (const tag of await page.locator(".history-tag").all()) {
      const box = await tag.boundingBox();
      expect(box.height).toBeGreaterThanOrEqual(44);
      expect(box.width).toBeGreaterThanOrEqual(44);
    }
    await page.screenshot({
      path: `test-results/screenshots/medicines-${width}-en.png`,
      fullPage: true,
    });
    await next(page);
    await page.goBack();
    await expect(pain).toBeChecked();
    await page.reload();
    await expect(pain).toBeChecked();
    await expect(page.getByLabel("Medicine name")).toHaveValue(
      "My original medicine",
    );
    for (let i = 0; i < 3; i++) await next(page);
    const section = page.locator(".summary section").filter({
      has: page.getByRole("heading", { name: "Medicines", exact: true }),
    });
    await expect(section).toContainText("Selected medicine types");
    await expect(section).toContainText("Entered medicine details");
    await expect(section).toContainText("My original medicine");
    await page.locator(".approval input").check();
    await section.getByRole("button").click();
    await pain.uncheck();
    await page.locator(".actions .primary").click();
    await expect(page.locator(".approval input")).not.toBeChecked();
  });
test("type-only, empty and explicit responses; legacy item add/edit/delete and preserved drafts", async ({
  page,
}) => {
  await setup(page, {
    status: "answered",
    value: "",
    items: [{ name: "Legacy name", detail: "Legacy dose" }],
  });
  await expect(page.getByLabel("Medicine name")).toHaveValue("Legacy name");
  await page.getByLabel("Medicine name").fill("Edited legacy");
  await page.getByRole("button", { name: /Add Medicines/ }).click();
  await page.getByLabel("Medicine name").nth(1).fill("Second");
  await page
    .getByRole("button", { name: "Remove item 2", exact: true })
    .click();
  const pain = page.getByRole("checkbox", { name: "Pain relief", exact: true });
  await pain.check();
  for (const [name, status] of [
    ["No current medicines", "none"],
    ["Not sure", "unknown"],
    ["Prefer not to answer", "declined"],
  ]) {
    await page.getByRole("button", { name, exact: true }).click();
    await expect(pain).not.toBeChecked();
    const a = (await read(page)).medicines;
    expect(a.status).toBe(status);
    expect(a.items[0].name).toBe("Edited legacy");
    for (let i = 0; i < 3; i++) await next(page);
    await expect(page.locator(".summary")).not.toContainText("Edited legacy");
    await expect(page.locator(".summary")).not.toContainText("Pain relief");
    await page
      .getByRole("button", { name: "Edit Medicines", exact: true })
      .click();
    await page
      .getByRole("button", { name: "Edit medicine types and details" })
      .click();
    await expect(pain).toBeChecked();
    await expect(page.getByLabel("Medicine name")).toHaveValue("Edited legacy");
    await page.goto("/#medicines");
  }
  await page
    .getByRole("button", { name: "Remove item 1", exact: true })
    .click();
  expect((await read(page)).medicines.items).toEqual([]);
  await next(page);
  await expect(page).toHaveURL(/#allergies$/);
  await page.goBack();
  await pain.uncheck();
  await next(page);
  expect((await read(page)).medicines.status).toBe("unanswered");
});

test("account medicine resume, immutable submission and doctor originals", async ({
  page,
}) => {
  const { seedDatabase, ACCOUNT_KEY } =
    await import("../../src/account/domain.js");
  const db = seedDatabase();
  const record = db.intakes.find((i) => i.id === "intake-a-draft");
  const d = initial();
  d.reasons = ["Medicine handoff"];
  for (const key of [
    "onset",
    "course",
    "severity",
    "impact",
    "history",
    "allergies",
    "questions",
  ])
    d[key].status = "unknown";
  record.data = d;
  record.step = "medicines";
  await page.addInitScript(
    ({ key, db }) => {
      if (!sessionStorage.getItem(key))
        sessionStorage.setItem(key, JSON.stringify(db));
    },
    { key: ACCOUNT_KEY, db },
  );
  await page.goto("/#/intakes/intake-a-draft/edit/medicines");
  await page.locator("#email").fill("garam@example.test");
  await page.locator("#password").fill("Demo1234!");
  await page.getByRole("button", { name: "Log in", exact: true }).click();
  await page
    .getByRole("checkbox", { name: "Diabetes medication", exact: true })
    .check();
  await page.getByRole("button", { name: /Add Medicines/ }).click();
  await page.getByLabel("Medicine name").fill("Patient supplied name");
  await page
    .getByLabel("Dose and how you take it")
    .fill("Patient supplied instructions");
  await page.getByRole("button", { name: /Save and go to my notes/ }).click();
  await page.goto("/#/intakes/intake-a-draft/edit/medicines");
  await page.reload();
  await expect(
    page.getByRole("checkbox", { name: "Diabetes medication", exact: true }),
  ).toBeChecked();
  await expect(page.getByLabel("Medicine name")).toHaveValue(
    "Patient supplied name",
  );
  const saved = await page.evaluate(
    (key) => sessionStorage.getItem(key),
    ACCOUNT_KEY,
  );
  await page.locator("#ui-language").selectOption("ko");
  expect(
    await page.evaluate((key) => sessionStorage.getItem(key), ACCOUNT_KEY),
  ).toBe(saved);
  await page.locator("#ui-language").selectOption("en");
  for (let i = 0; i < 3; i++) await next(page);
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
  expect(snapshot.data.medicines.tags).toEqual(["diabetes-medication"]);
  expect(snapshot.data.medicines.items[0].name).toBe("Patient supplied name");
  await page.goto("/#/intakes/intake-a-draft/edit/medicines");
  await expect(page).toHaveURL(/#\/intakes\/intake-a-draft$/);
  await page.getByRole("button", { name: "Log out", exact: true }).click();
  await page.getByRole("button", { name: /Demo doctor/ }).click();
  await page.getByRole("button", { name: "Log in", exact: true }).click();
  await expect(page).toHaveURL(/#\/doctor$/);
  await page.goto("/#/doctor/appointments/apt-a-next");
  await expect(page.locator(".doctor-summary")).toContainText(
    "Selected medicine types",
  );
  await expect(page.locator(".doctor-summary")).toContainText(
    "Diabetes medication",
  );
  await expect(page.locator(".doctor-summary")).toContainText(
    "Patient supplied name",
  );
  await page
    .getByRole("button", { name: "Show all original answers", exact: true })
    .click();
  await expect(page.locator(".doctor-original")).toContainText(
    "Entered medicine details",
  );
  await expect(page.locator(".doctor-original")).toContainText(
    "Patient supplied instructions",
  );
  await page.locator("#ui-language").selectOption("ko");
  await expect(page.locator(".doctor-original")).toContainText("당뇨약");
  await expect(page.locator(".doctor-original")).toContainText(
    "Patient supplied name",
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

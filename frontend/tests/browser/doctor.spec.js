import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
async function login(page, path = "/doctor") {
  await page.goto("/#" + path);
  await page.getByLabel("Email", { exact: true }).fill("doctor@example.test");
  await page.getByLabel("Password", { exact: true }).fill("Demo1234!");
  await page
    .getByRole("button", { name: "Log in", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Patient queue" }),
  ).toBeVisible();
}
const patient = (page, name) =>
  page.getByRole("link").filter({ has: page.getByText(name, { exact: true }) });
async function open(page, name = "Ari Demo") {
  await patient(page, name).click();
  await expect(page.getByRole("heading", { name, exact: true })).toBeVisible();
}
test("doctor search, sources, note failure/retry, review and new submission", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await login(page);
  await page.getByLabel("Patient name or ID").fill("DEMO-001");
  await expect(patient(page, "Bo Demo")).toHaveCount(0);
  await open(page);
  await page
    .getByRole("button", {
      name: "View original answers: Visit purpose & priorities",
      exact: true,
    })
    .click();
  await expect(page.locator(".source-highlight")).toContainText(
    "Headache affecting my work",
  );
  await page
    .getByRole("button", {
      name: "View original answers: Medicines",
      exact: true,
    })
    .click();
  await expect(page.locator(".source-highlight")).toHaveAttribute(
    "id",
    /:medicines$/,
  );
  await expect(page.locator(".source-highlight")).toBeFocused();
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await expect(page.locator(".source-highlight")).toBeInViewport();
  await page.screenshot({
    path: "test-results/screenshots/doctor-original-1440.png",
    fullPage: false,
  });
  await page
    .getByLabel("Doctor’s preparation note", { exact: true })
    .fill("Ask about sleep.");
  await page
    .locator(".doctor-detail")
    .getByText("Demo controls", { exact: true })
    .click();
  await page
    .getByRole("button", { name: "Fail next note save", exact: true })
    .click();
  await page.getByRole("button", { name: "Save note", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("demo request failed");
  await expect(
    page.getByLabel("Doctor’s preparation note", { exact: true }),
  ).toHaveValue("Ask about sleep.");
  await page.getByRole("button", { name: "Save note", exact: true }).click();
  await expect(
    page.getByText("Saved in this demo", { exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Mark as reviewed", exact: true })
    .click();
  await expect(page.locator(".review-record")).toContainText("doctor-demo");
  await expect(patient(page, "Ari Demo")).toContainText("Reviewed");
  await page
    .getByRole("button", { name: "Simulate a new submission", exact: true })
    .click();
  await expect(
    page.getByText("A new submission has arrived.", { exact: false }),
  ).toBeVisible();
  await expect(patient(page, "Ari Demo")).toContainText("Awaiting review");
  await page
    .getByRole("button", { name: "Open latest submission", exact: true })
    .click();
  await expect(
    page.getByLabel("Doctor’s preparation note", { exact: true }),
  ).toHaveValue("");
  await expect(page.locator(".review-record")).toHaveCount(0);
  await page
    .getByLabel("Submission version", { exact: true })
    .selectOption({ index: 0 });
  await expect(
    page.getByLabel("Doctor’s preparation note", { exact: true }),
  ).toHaveValue("Ask about sleep.");
  await expect(page.locator(".review-record")).toHaveCount(1);
});
test("dirty navigation, language, stored note, rapid patient transition and denied IDs", async ({
  page,
}) => {
  await login(page);
  await open(page);
  const note = page.getByLabel("Doctor’s preparation note", { exact: true });
  await note.fill("Do not translate this note.");
  await page.locator("#ui-language").selectOption("ko");
  await expect(page.locator("#doctor-note")).toHaveValue(
    "Do not translate this note.",
  );
  await page.locator("#ui-language").selectOption("en");
  await patient(page, "Bo Demo").click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.getByRole("button", { name: "Keep editing", exact: true }).click();
  await expect(note).toBeFocused();
  await patient(page, "Bo Demo").click();
  await page
    .getByRole("button", { name: "Save and leave", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Bo Demo", exact: true }),
  ).toBeVisible();
  await expect(note).toHaveValue("");
  await open(page);
  await expect(note).toHaveValue("Do not translate this note.");
  await page
    .locator(".doctor-detail")
    .getByText("Demo controls", { exact: true })
    .click();
  await page
    .getByRole("button", { name: "Delay next request", exact: true })
    .click();
  await patient(page, "Bo Demo").click();
  await patient(page, "Ari Demo").click();
  await expect(
    page.getByRole("heading", { name: "Ari Demo", exact: true }),
  ).toBeVisible();
  await page.waitForTimeout(1500);
  await expect(note).toHaveValue("Do not translate this note.");
  await page.goto("/#/doctor/appointments/doctor-apt-private");
  await expect(page.getByRole("alert")).toContainText("access not permitted");
  await expect(page.getByText("Restricted demo patient")).toHaveCount(0);
});
test("direct login return, unsubmitted, unavailable summary, session expiry", async ({
  page,
}) => {
  await login(page, "/doctor/appointments/doctor-apt-3");
  await expect(
    page.getByText("No intake has been submitted.", { exact: false }),
  ).toBeVisible();
  await expect(page.locator("#doctor-note")).toHaveCount(0);
  await open(page, "Ellis Demo");
  await expect(
    page.getByText("Summary generation failed.", { exact: false }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Show all original answers", exact: true })
    .click();
  await expect(
    page.getByRole("heading", {
      name: "Patient’s original answers",
      exact: true,
    }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Try again", exact: true }).click();
  await expect(
    page.getByRole("heading", {
      name: "Visit purpose & priorities",
      exact: true,
    }),
  ).toBeVisible();
  await page
    .locator(".doctor-detail")
    .getByText("Demo controls", { exact: true })
    .click();
  await page
    .getByRole("button", { name: "Expire session", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Welcome back", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Ellis Demo", exact: true }),
  ).toHaveCount(0);
});
for (const width of [360, 900, 1440])
  test(`doctor responsive keyboard and accessibility ${width}`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 1000 });
    await login(page);
    await page.locator(".doctor-app .skip").focus();
    await page.keyboard.press("Enter");
    await expect(page.locator("#doctor-main")).toBeFocused();
    await patient(page, "Ari Demo").focus();
    await page.keyboard.press("Enter");
    await expect(
      page.getByRole("heading", { name: "Ari Demo", exact: true }),
    ).toBeVisible();
    await page.locator("#doctor-note").fill("Keyboard note");
    await page.getByRole("button", { name: "Save note", exact: true }).focus();
    await page.keyboard.press("Enter");
    await expect(
      page.getByText("Saved in this demo", { exact: true }),
    ).toBeVisible();
    for (const locale of ["en", "ko"]) {
      await page.locator("#ui-language").selectOption(locale);
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth,
        ),
      ).toBe(true);
      const result = await new AxeBuilder({ page }).analyze();
      expect(result.violations).toEqual([]);
      await page.evaluate(() => window.scrollTo(0, 0));
      await page.screenshot({
        path: `test-results/screenshots/doctor-${width}-${locale}.png`,
        fullPage: true,
      });
    }
    await page.reload();
    await expect(page.locator("html")).toHaveAttribute("lang", "ko");
    await expect(page.locator("#doctor-note")).toHaveValue("Keyboard note");
    expect(
      await page.evaluate(async () => [
        ...(await import("/src/i18n/core.js")).missingKeys,
      ]),
    ).toEqual([]);
  });

test("queue filters, empty date, loading failure, keyboard logout and back navigation guard", async ({
  page,
}) => {
  await login(page, "/doctor/login");
  await page
    .getByLabel("Review filter", { exact: true })
    .selectOption("unsubmitted");
  await expect(patient(page, "Casey Demo")).toBeVisible();
  await expect(patient(page, "Ari Demo")).toHaveCount(0);
  await page.getByLabel("Patient name or ID").fill("No such demo");
  await expect(
    page.getByText("No matching patients.", { exact: false }),
  ).toBeVisible();
  await page.getByLabel("Patient name or ID").fill("");
  await page.getByLabel("Review filter", { exact: true }).selectOption("all");
  const date = await page.locator("#doctor-date").inputValue();
  await page.locator("#doctor-date").fill("2035-01-01");
  await expect(
    page.getByText("No appointments on this date.", { exact: false }),
  ).toBeVisible();
  await page.locator("#doctor-date").fill(date);
  await page
    .locator(".doctor-queue")
    .getByText("Demo controls", { exact: true })
    .click();
  await page
    .locator(".doctor-queue")
    .getByRole("button", { name: "Fail next reload", exact: true })
    .click();
  await expect(page.locator(".doctor-queue").getByRole("alert")).toBeVisible();
  await page.getByRole("button", { name: "Try again", exact: true }).click();
  await open(page);
  await page.locator("#doctor-note").fill("Unsaved");
  await page.goBack();
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.getByRole("button", { name: "Keep editing", exact: true }).click();
  await expect(page.locator("#doctor-note")).toHaveValue("Unsaved");
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await page
    .getByRole("button", { name: "Discard changes and leave", exact: true })
    .focus();
  await page.keyboard.press("Enter");
  await expect(
    page.getByRole("heading", { name: "Welcome back", exact: true }),
  ).toBeVisible();
  await page.goBack();
  await expect(
    page.getByRole("heading", { name: "Ari Demo", exact: true }),
  ).toHaveCount(0);
});

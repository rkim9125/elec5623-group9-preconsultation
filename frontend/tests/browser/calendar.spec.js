import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
async function login(page) {
  await page.goto("/#/doctor");
  await page.getByLabel("Email", { exact: true }).fill("doctor@example.test");
  await page.getByLabel("Password", { exact: true }).fill("Demo1234!");
  await page.getByRole("button", { name: "Log in", exact: true }).click();
  await expect(page.locator(".calendar-day-list .calendar-event")).toHaveCount(
    5,
  );
}
const event = (page, name) =>
  page
    .locator(".calendar-day-list")
    .getByRole("button", { name: new RegExp(name) });
const panel = (page) => page.locator(".calendar-inspector");
test("month navigation, more, exact selection, language and intake round trip", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await login(page);
  const month = await page.locator(".calendar-heading h2").textContent();
  await page.getByRole("button", { name: "+3 more", exact: true }).click();
  await expect(page.locator(".calendar-day-list")).toBeFocused();
  await event(page, "Bo Demo").click();
  await expect(panel(page)).toContainText("Bo Demo");
  await expect(panel(page)).toContainText("Reviewed");
  await event(page, "Casey Demo").click();
  await expect(panel(page)).not.toContainText("Bo Demo");
  await expect(panel(page)).toContainText("No intake has been submitted.");
  await event(page, "Ari Demo").click();
  await expect(panel(page)).toContainText("Ari Demo");
  await page.locator("#ui-language").selectOption("ko");
  await expect(panel(page)).toContainText("Ari Demo");
  await panel(page).getByRole("link", { name: "문진 상세 보기" }).click();
  await expect(page.locator("#doctor-note")).toBeVisible();
  await page.goBack();
  await expect(panel(page)).toContainText("Ari Demo");
  await page.locator("#ui-language").selectOption("en");
  await expect(page.locator(".calendar-heading h2")).toHaveText(month);
  await page.getByRole("button", { name: "Next month", exact: true }).click();
  await page.getByRole("button", { name: "Next month", exact: true }).click();
  await expect(panel(page)).toContainText("Select an appointment");
  await page.getByRole("button", { name: "Today", exact: true }).click();
  await expect(page.locator(".calendar-heading h2")).toHaveText(month);
  await expect(panel(page)).toContainText("Select an appointment");
  await expect(page.locator('.calendar-day[aria-current="date"]')).toHaveCount(
    1,
  );
});
test("stale month/detail requests, failures and retry preserve month, session cleanup", async ({
  page,
}) => {
  await login(page);
  await page.evaluate(async () => {
    const { doctorService: api } = await import("/src/doctor/service.js");
    const original = api.listRange;
    api.listRange = async (...args) => {
      const rows = await original(...args);
      await new Promise((r) =>
        setTimeout(r, args[1].includes("-09-") ? 900 : 10),
      );
      return rows;
    };
    api.slowNext();
  });
  await page.getByRole("button", { name: "Next month", exact: true }).click();
  await page.getByRole("button", { name: "Next month", exact: true }).click();
  const month = await page.locator(".calendar-heading h2").textContent();
  await page.waitForTimeout(1600);
  await expect(page.locator(".calendar-heading h2")).toHaveText(month);
  await expect(page.locator(".calendar-day-list .calendar-event")).toHaveCount(
    0,
  );
  await page.locator(".calendar-main details summary").click();
  await page.getByRole("button", { name: "Fail next calendar reload" }).click();
  await expect(page.locator('.calendar-main [role="alert"]')).toBeVisible();
  await page
    .locator(".calendar-main")
    .getByRole("button", { name: "Try again", exact: true })
    .click();
  await expect(page.locator('.calendar-main [role="alert"]')).toHaveCount(0);
  await expect(page.locator(".calendar-heading h2")).toHaveText(month);
  await page.getByRole("button", { name: "Today", exact: true }).click();
  await expect(event(page, "Ari Demo")).toBeVisible();
  await page.evaluate(async () =>
    (await import("/src/doctor/service.js")).doctorService.slowNext(),
  );
  await event(page, "Ari Demo").click();
  await event(page, "Bo Demo").click();
  await expect(panel(page)).toContainText("Bo Demo");
  await page.waitForTimeout(1500);
  await expect(panel(page)).not.toContainText("Ari Demo");
  await panel(page).locator("summary").click();
  await panel(page)
    .getByRole("button", { name: "Fail next reload", exact: true })
    .click();
  await expect(panel(page).getByRole("alert")).toBeVisible();
  await expect(panel(page)).not.toContainText("Bo Demo");
  await panel(page)
    .getByRole("button", { name: "Try again", exact: true })
    .click();
  await expect(panel(page)).toContainText("Bo Demo");
  await page
    .getByRole("button", { name: "Expire session", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Welcome back" }),
  ).toBeVisible();
  await expect(page.locator(".calendar-workspace")).toHaveCount(0);
});
for (const width of [360, 900, 1440])
  test(`calendar responsive keyboard and accessibility ${width}`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 1000 });
    await login(page);
    await page.screenshot({
      path: `test-results/screenshots/calendar-${width}-default.png`,
      fullPage: true,
    });
    await event(page, "Ari Demo").focus();
    await page.keyboard.press("Space");
    await expect(panel(page)).toContainText("Ari Demo");
    if (width === 360) await expect(panel(page)).toBeFocused();
    else await expect(event(page, "Ari Demo")).toBeFocused();
    for (const locale of ["en", "ko"]) {
      await page.locator("#ui-language").selectOption(locale);
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth,
        ),
      ).toBe(true);
      expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
      await expect(panel(page)).toContainText("Ari Demo");
      await expect(
        page.locator(".calendar-day-list .calendar-event"),
      ).toHaveCount(5);
      await page.evaluate(() => window.scrollTo(0, 0));
      await page.screenshot({
        path: `test-results/screenshots/calendar-${width}-${locale}-selected.png`,
        fullPage: true,
      });
    }
    expect(
      await page.evaluate(async () => [
        ...(await import("/src/i18n/core.js")).missingKeys,
      ]),
    ).toEqual([]);
  });
test("same-range refresh retains selection, deletion clears it, 200 percent layout", async ({
  page,
}) => {
  await login(page);
  await event(page, "Ari Demo").click();
  await expect(panel(page)).toContainText("Ari Demo");
  await page.evaluate(async () =>
    (await import("/src/doctor/service.js")).doctorService.simulateSubmission(
      (await import("/src/doctor/service.js")).doctorService.scope(),
      "doctor-apt-1",
    ),
  );
  await expect(
    panel(page).locator("dd").filter({ hasText: /^2$/ }),
  ).toHaveCount(1);
  await expect(panel(page)).toContainText("Ari Demo");
  await page.evaluate(async () => {
    const { doctorService: api } = await import("/src/doctor/service.js");
    const original = api.listRange;
    api.listRange = async (...args) =>
      (await original(...args)).filter((a) => a.id !== "doctor-apt-1");
    api.simulateSubmission(api.scope(), "doctor-apt-1");
  });
  await expect(panel(page)).toContainText("no longer available");
  await expect(panel(page)).not.toContainText("Ari Demo");
  await page.setViewportSize({ width: 720, height: 500 });
  // A 1440px desktop at 200% browser zoom has a 720 CSS-pixel viewport.
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
});

test("stored past/completed status, draft privacy and denied detail selection", async ({
  page,
}) => {
  await login(page);
  for (const [id, status] of [
    ["apt-a-past", "Past appointment · completion unconfirmed"],
    ["apt-b-past", "Visit completed"],
    ["apt-a-next", "Upcoming"],
  ]) {
    const row = await page.evaluate(async (id) => {
      const { doctorService: api, dayKey } =
        await import("/src/doctor/service.js");
      const a = await api.detail(api.scope(), id);
      return {
        name: a.patient.name,
        day: dayKey(a.startsAt),
        dateLabel: new Intl.DateTimeFormat("en-GB", {
          dateStyle: "full",
          timeZone: "Asia/Seoul",
        }).format(new Date(a.startsAt)),
      };
    }, id);
    // Use the complete localized accessible date to avoid adjacent-month ambiguity.
    await page
      .getByRole("button", { name: new RegExp(`^${row.dateLabel},`) })
      .click();
    await event(page, row.name).first().click();
    await expect(
      panel(page).getByText(status, { exact: true }).first(),
    ).toBeVisible();
    if (id === "apt-a-next") {
      await expect(panel(page)).toContainText("No intake has been submitted.");
      await expect(panel(page)).not.toContainText("오후에 머리가 불편해요");
    }
  }
  await page.getByRole("button", { name: "Today", exact: true }).click();
  await page.evaluate(async () => {
    const { doctorService: api } = await import("/src/doctor/service.js");
    const original = api.detail;
    api.detail = (scope, id) =>
      id === "doctor-apt-1"
        ? Promise.reject(
            Object.assign(new Error("NOT_FOUND"), { code: "NOT_FOUND" }),
          )
        : original(scope, id);
  });
  await event(page, "Ari Demo").click();
  await expect(panel(page)).toContainText("no longer available");
  await expect(panel(page)).not.toContainText("Ari Demo");
});

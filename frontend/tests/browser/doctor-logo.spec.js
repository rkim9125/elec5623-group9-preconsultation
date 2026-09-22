import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
async function login(page, doctor = true) {
  await page.goto(doctor ? "/#/doctor" : "/#/my");
  await page
    .getByLabel("Email", { exact: true })
    .fill(doctor ? "doctor@example.test" : "garam@example.test");
  await page.getByLabel("Password", { exact: true }).fill("Demo1234!");
  await page.getByRole("button", { name: "Log in", exact: true }).click();
  await expect(
    page.locator(doctor ? ".calendar-day-list .calendar-event" : ".portal-nav"),
  ).toHaveCount(doctor ? 5 : 1);
}
async function checkHeader(page, doctor, locale) {
  const header = page.locator("header.header");
  const brand = header.locator(".brand"),
    symbol = brand.locator(".brand-symbol");
  await expect(symbol).toHaveText("✳");
  await expect(symbol).toBeVisible();
  await expect(symbol).toHaveAttribute("aria-hidden", "true");
  await expect(brand).toHaveAccessibleName(
    new RegExp(locale === "en" ? "Visit Notes" : "진료노트"),
  );
  await expect(brand).toHaveAttribute("href", doctor ? "#/doctor" : "#/my");
  await page.evaluate(() => document.fonts.ready);
  const boxes = await Promise.all(
    [brand, header.locator("#ui-language"), header.locator("button")].map(
      (el) => el.boundingBox(),
    ),
  );
  const frame = await header.boundingBox();
  for (const box of boxes) {
    expect(box.x).toBeGreaterThanOrEqual(0);
    expect(box.x + box.width).toBeLessThanOrEqual(page.viewportSize().width);
    expect(box.y + box.height).toBeLessThanOrEqual(frame.y + frame.height + 1);
  }
  for (let i = 0; i < boxes.length; i++)
    for (let j = i + 1; j < boxes.length; j++) {
      const a = boxes[i],
        b = boxes[j];
      expect(
        a.x + a.width <= b.x ||
          b.x + b.width <= a.x ||
          a.y + a.height <= b.y ||
          b.y + b.height <= a.y,
      ).toBe(true);
    }
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  expect(
    (await new AxeBuilder({ page }).include("header.header").analyze())
      .violations,
  ).toEqual([]);
}
for (const width of [360, 900, 1440])
  test(`doctor logo, navigation and unsaved note protection ${width}`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 1000 });
    await login(page);
    for (const locale of ["en", "ko"]) {
      await page.locator("#ui-language").selectOption(locale);
      await checkHeader(page, true, locale);
      await page.screenshot({
        path: `../docs/screenshots/doctor-logo/after-${width}-${locale}.png`,
      });
    }
    await page.locator("#ui-language").selectOption("en");
    await page
      .locator(".calendar-day-list")
      .getByRole("button", { name: /Ari Demo/ })
      .click();
    await page
      .locator(".calendar-inspector")
      .getByRole("link", { name: "View intake details" })
      .click();
    await expect(page.locator("#doctor-note")).toBeVisible();
    for (const locale of ["en", "ko"]) {
      await page.locator("#ui-language").selectOption(locale);
      await checkHeader(page, true, locale);
      await page.screenshot({
        path: `../docs/screenshots/doctor-logo/detail-${width}-${locale}.png`,
      });
    }
    await page.locator("#ui-language").selectOption("en");
    await page.locator("#doctor-note").fill("Keep this unsaved note.");
    const brand = page.locator(".doctor-header .brand");
    await page.locator(".doctor-app .skip").focus();
    await page.keyboard.press("Tab");
    await expect(brand).toBeFocused();
    expect(
      await brand.evaluate((el) => getComputedStyle(el).outlineStyle),
    ).toBe("solid");
    await page.keyboard.press("Enter");
    await expect(page.getByRole("dialog")).toBeVisible();
    await page
      .getByRole("button", { name: "Keep editing", exact: true })
      .click();
    await expect(page.locator("#doctor-note")).toHaveValue(
      "Keep this unsaved note.",
    );
    await brand.click();
    await page
      .getByRole("button", { name: "Discard changes and leave", exact: true })
      .click();
    await expect(page).toHaveURL(/#\/doctor$/);
    await expect(page.locator(".calendar-inspector")).toContainText("Ari Demo");
    await expect(page.locator(".doctor-header a")).toHaveCount(1);
  });
test("existing patient logo and header stay intact", async ({ page }) => {
  await login(page, false);
  for (const width of [360, 900, 1440]) {
    await page.setViewportSize({ width, height: 1000 });
    for (const locale of ["en", "ko"]) {
      await page.locator("#ui-language").selectOption(locale);
      await checkHeader(page, false, locale);
      await page
        .locator("header.header")
        .screenshot({
          path: `../docs/screenshots/doctor-logo/patient-${width}-${locale}.png`,
        });
    }
  }
});

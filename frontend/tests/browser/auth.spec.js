import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
async function signIn(page, email) {
  await page.locator("#email").fill(email);
  await page.locator("#password").fill("Demo1234!");
  await page.getByRole("button", { name: "Log in", exact: true }).click();
}
test("unified patient/doctor login, role guard, account switching and back after logout", async ({
  page,
}) => {
  await page.goto("/#/login");
  await expect(
    page.getByRole("link", { name: "Doctor sign in", exact: true }),
  ).toHaveCount(0);
  await signIn(page, "garam@example.test");
  await expect(page).toHaveURL(/#\/my$/);
  await page.goto("/#/doctor/appointments/doctor-apt-1");
  await expect(page).toHaveURL(/#\/my$/);
  await page.getByRole("button", { name: "Log out", exact: true }).click();
  await page.getByRole("button", { name: /Demo doctor/ }).click();
  await expect(page.locator("#email")).toHaveValue("doctor@example.test");
  await expect(page.locator("#password")).toHaveValue("Demo1234!");
  await expect(page).toHaveURL(/#\/login$/);
  await page.getByRole("button", { name: "Log in", exact: true }).click();
  await expect(page).toHaveURL(/#\/doctor$/);
  await expect(
    page.getByRole("link", { name: "Patient service", exact: true }),
  ).toHaveCount(0);
  await page.goto("/#/intakes/intake-a-draft");
  await expect(page).toHaveURL(/#\/doctor$/);
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await signIn(page, "narae@example.test");
  await expect(page).toHaveURL(/#\/my$/);
  await expect(page.locator(".doctor-workspace")).toHaveCount(0);
  await expect(page.locator(".portal-nav-bottom")).toContainText("나래");
  await page.getByRole("button", { name: "Log out", exact: true }).click();
  await page.goBack();
  await expect(page.locator(".portal-nav-bottom")).toHaveCount(0);
  await expect(page.locator(".doctor-workspace")).toHaveCount(0);
});
for (const width of [360, 1440])
  test(`auth language, keyboard, validation and doctor deep link ${width}`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 900 });
    await page.goto("/#/doctor/appointments/doctor-apt-1");
    await expect(page).toHaveURL(/#\/login\?returnTo=/);
    const url = page.url();
    await page.getByRole("button", { name: "Log in", exact: true }).click();
    await expect(page.locator("#email")).toBeFocused();
    await page.getByRole("button", { name: /Demo doctor/ }).focus();
    await page.keyboard.press("Enter");
    await page.locator("#ui-language").selectOption("ko");
    await expect(page.getByRole("button", { name: /데모 의사/ })).toBeVisible();
    await expect(page.locator("#email")).toHaveValue("doctor@example.test");
    await expect(page.locator("#password")).toHaveValue("Demo1234!");
    expect(page.url()).toBe(url);
    expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    await page.screenshot({
      path: `test-results/screenshots/auth-${width}-ko.png`,
      fullPage: true,
    });
    await page.locator("#ui-language").selectOption("en");
    await page.getByRole("button", { name: "Log in", exact: true }).focus();
    await page.keyboard.press("Enter");
    await expect(page).toHaveURL(/#\/doctor\/appointments\/doctor-apt-1$/);
    await expect(
      page.getByRole("heading", { name: "Ari Demo", exact: true }),
    ).toBeVisible();
  });
test("legacy login redirects and patient detail return is preserved", async ({
  page,
}) => {
  await page.goto("/#/doctor/login");
  await expect(page).toHaveURL(/#\/login$/);
  await page.goto("/#/appointments/apt-a-next");
  await signIn(page, "garam@example.test");
  await expect(page).toHaveURL(/#\/appointments\/apt-a-next$/);
  await expect(page.locator(".portal-main")).toBeVisible();
});

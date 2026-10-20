import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
const fixture = "/tests/browser/fixtures/body-map.html";
const zone = (page, label) =>
  page.locator(".bm-zones").getByRole("button", { name: label, exact: true });
const row = (page, label) =>
  page.locator(".bm-list").getByRole("button", { name: label, exact: true });
test("multiple selections, view preservation, orientation, keyboard and clear", async ({
  page,
}) => {
  await page.goto(fixture);
  await expect(page.locator(".bm-result")).toContainText("No area selected");
  await expect(
    page.getByRole("button", { name: "Clear", exact: true }),
  ).toBeDisabled();
  const knee = zone(page, "Right Knee · Front");
  await knee.click();
  await expect(knee).toBeFocused();
  await expect(row(page, "Right Knee · Front")).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  await expect(page.locator(".bm-result")).toContainText("Right Knee · Front");
  await knee.press("Space");
  await expect(knee).toHaveAttribute("aria-pressed", "false");
  await knee.press("Space");
  await expect(knee).toHaveAttribute("aria-pressed", "true");
  await page.getByRole("button", { name: "Back", exact: true }).click();
  await expect(page.locator(".bm-sides span").first()).toHaveText("Your left");
  await expect(
    page.locator(".bm-zones [aria-pressed=true], .bm-list [aria-pressed=true]"),
  ).toHaveCount(0);
  await expect(page.locator(".bm-result")).toContainText("Right Knee · Front");
  await page.getByRole("button", { name: "Front", exact: true }).click();
  await expect(knee).toHaveAttribute("aria-pressed", "true");
  await page.getByRole("button", { name: "Back", exact: true }).click();
  const calf = row(page, "Left Calf · Back");
  await calf.focus();
  await calf.press("Enter");
  await expect(calf).toBeFocused();
  await expect(zone(page, "Left Calf · Back")).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  expect((await zone(page, "Left Calf · Back").boundingBox()).x).toBeLessThan(
    (await zone(page, "Right Calf · Back").boundingBox()).x,
  );
  await expect(page.locator(".bm-result")).toContainText("Left Calf · Back");
  await expect(page.locator(".bm-result")).toContainText("Right Knee · Front");
  await expect(page.locator(".bm-selected-areas li")).toHaveCount(2);
  await calf.press("Tab");
  await expect(row(page, "Right Ankle · Back")).toBeFocused();
  await page
    .getByRole("button", { name: "Remove Right Knee · Front", exact: true })
    .click();
  await expect(page.locator(".bm-selected-areas li")).toHaveCount(1);
  await expect(page.locator(".bm-result")).toContainText("Left Calf · Back");
  await page.getByRole("button", { name: "Clear", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Back", exact: true }),
  ).toBeFocused();
  await expect(page.locator(".bm-result")).toContainText("No area selected");
  const results = await new AxeBuilder({ page })
    .include(".lower-body-map")
    .analyze();
  expect(results.violations).toEqual([]);
});
for (const width of [320, 390, 768])
  test(`layout and reference capture ${width}`, async ({ page }) => {
    await page.setViewportSize({ width, height: 1200 });
    await page.goto(fixture);
    await zone(page, "Right Knee · Front").click();
    await page.screenshot({
      path: `test-results/body-${width}.png`,
      fullPage: true,
      animations: "disabled",
    });
    await page.getByRole("button", { name: "Back", exact: true }).click();
    await row(page, "Left Back of knee · Back").click();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    const map = await page.locator(".bm-map").boundingBox(),
      list = await page.locator(".bm-list").boundingBox();
    if (width <= 560) expect(list.y).toBeGreaterThan(map.y + map.height);
    else expect(list.x).toBeGreaterThan(map.x + map.width);
    for (const button of await page.locator(".bm-row button").all()) {
      const box = await button.boundingBox();
      expect(box.width).toBeGreaterThanOrEqual(44);
      expect(box.height).toBeGreaterThanOrEqual(44);
    }
    await page.screenshot({
      path: `test-results/body-back-${width}.png`,
      fullPage: true,
      animations: "disabled",
    });
  });
test("narrow parent, reduced motion and guided form integration", async ({
  page,
}) => {
  await page.setViewportSize({ width: 768, height: 1200 });
  await page.goto(fixture + "?guided");
  await page.locator("#root").evaluate((el) => (el.style.width = "300px"));
  await row(page, "Right Knee · Front").click();
  await page.getByRole("button", { name: "Back", exact: true }).click();
  await row(page, "Left Back of knee · Back").click();
  await expect(page.locator(".bm-result")).toContainText(
    "Left Back of knee · Back",
  );
  await expect(page.getByTestId("saved-answer")).toContainText(
    "- Right knee · Front",
  );
  await expect(page.getByTestId("saved-answer")).toContainText(
    "- Left back of knee · Back",
  );
  const map = await page.locator(".bm-map").boundingBox(),
    list = await page.locator(".bm-list").boundingBox();
  expect(list.y).toBeGreaterThan(map.y + map.height);
  expect(
    await page
      .locator("#root")
      .evaluate((el) => el.scrollWidth <= el.clientWidth),
  ).toBe(true);
  await page.emulateMedia({ reducedMotion: "reduce" });
  expect(
    await row(page, "Left Back of knee · Back").evaluate(
      (el) => getComputedStyle(el).transitionDuration,
    ),
  ).toBe("0s");
  await page.screenshot({
    path: "test-results/body-narrow-parent.png",
    fullPage: true,
    animations: "disabled",
  });
});

test("initial selection in uncontrolled use retains its original view", async ({
  page,
}) => {
  await page.goto(fixture + "?initial");
  await expect(page.locator(".bm-result")).toContainText("Left Calf · Back");
  await expect(page.locator(".bm-zones [aria-pressed=true]")).toHaveCount(0);
  await page.getByRole("button", { name: "Back", exact: true }).click();
  await expect(zone(page, "Left Calf · Back")).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  await row(page, "Right Foot · Back").click();
  await expect(page.locator(".bm-result")).toContainText("Right Foot · Back");
  await expect(page.locator(".bm-result")).toContainText("Left Calf · Back");
});

test("legacy locations and authored details survive adding multiple locations", async ({
  page,
}) => {
  await page.goto(fixture + "?guided&legacy");
  await row(page, "Right Knee · Front").click();
  await row(page, "Left Knee · Front").click();
  await expect(page.getByTestId("saved-answer")).toHaveText(
    "Selected options:\n- Right knee · Front\n- Left knee · Front\n\nAdditional details:\nRight knee\nPatient’s original detail.",
  );
});

for (const original of ["", "O", "AB-"])
  test(`blood profile preserves known ABO and optional Rh: ${original || "empty"}`, async ({
    page,
  }) => {
    await page.route("**/api/v1/auth/profile", async (route) => {
      const profile =
        route.request().method() === "PUT"
          ? route.request().postDataJSON()
          : { blood_group: original };
      await route.fulfill({ json: { profile } });
    });
    await page.goto(fixture + "?profile");
    await page.getByRole("button", { name: "Continue", exact: true }).click();
    await page.getByRole("button", { name: "Continue", exact: true }).click();
    if (!original) {
      await expect(
        page.getByRole("group", { name: "Rh factor (optional)" }),
      ).toHaveCount(0);
      await page.getByRole("button", { name: "O", exact: true }).click();
    }
    const rh = page.getByRole("group", { name: "Rh factor (optional)" });
    await expect(
      rh.getByRole("button", {
        name: original === "AB-" ? "Negative (−)" : "I don’t know",
        exact: true,
      }),
    ).toHaveAttribute("aria-pressed", "true");
    for (let step = 0; step < 5; step++)
      await page.getByRole("button", { name: "Continue", exact: true }).click();
    await page
      .getByRole("button", { name: "Save profile", exact: true })
      .click();
    await expect(page.locator("output")).toContainText(
      `"blood_group":"${original || "O"}"`,
    );
  });

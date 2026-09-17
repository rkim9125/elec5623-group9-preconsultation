import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { readFile } from "node:fs/promises";

test.setTimeout(60000);
test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    window.demoWriteCount = 0;
    const original = Storage.prototype.setItem;
    Storage.prototype.setItem = function (key, value) {
      if (key !== "visit-notes-language") window.demoWriteCount++;
      return original.call(this, key, value);
    };
  });
});
const language = (page) => page.locator("#ui-language");
const switchTo = async (page, locale) => {
  await language(page).focus();
  await language(page).selectOption(locale);
  await expect(page.locator("html")).toHaveAttribute("lang", locale);
  await expect(language(page)).toBeFocused();
};
const next = (page) => page.getByRole("button", { name: /^Continue/ }).click();
async function snapshot(page) {
  return page.evaluate(() => ({
    hash: location.hash,
    session: { ...sessionStorage },
    writes: window.demoWriteCount,
  }));
}
async function noOverflow(page) {
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
}
async function noMissing(page) {
  expect(
    await page.evaluate(async () => [
      ...(await import("/src/i18n/core.js")).missingKeys,
    ]),
  ).toEqual([]);
}
async function login(page) {
  await page.goto("/#/login");
  await page.getByRole("button", { name: /데모 가람/ }).click();
  await page.getByRole("button", { name: "Log in", exact: true }).click();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(
    "Hello, 데모 가람.",
  );
}

test("English default, invalid setting, signup/login, errors, persistence and keyboard control", async ({
  page,
  context,
}) => {
  await page.goto("/#/signup");
  await expect(language(page)).toHaveValue("en");
  await expect(language(page).locator("option")).toHaveText([
    "English",
    "korean",
  ]);
  await page.getByLabel("Name", { exact: true }).fill("테스트 이름");
  await page.getByLabel("Email", { exact: true }).fill("invalid");
  await page.getByRole("button", { name: "Sign up", exact: true }).click();
  await expect(
    page.getByText("Use an email address such as name@example.test."),
  ).toBeVisible();
  await language(page).focus();
  await page.keyboard.press("k");
  await page.keyboard.press("Tab");
  await expect(page.locator("html")).toHaveAttribute("lang", "ko");
  await expect(page.getByLabel("이름", { exact: true })).toHaveValue(
    "테스트 이름",
  );
  await expect(
    page.getByText("이름@example.test 형식으로 입력해 주세요."),
  ).toBeVisible();
  await expect(page).toHaveTitle(/내 진료노트 시작하기/);
  await switchTo(page, "en");
  await page.getByLabel("Email", { exact: true }).fill("language@example.test");
  await page.getByLabel("Password", { exact: true }).fill("Example123");
  await page.getByLabel("Confirm password", { exact: true }).fill("Example123");
  await switchTo(page, "ko");
  await expect(page.locator("#password")).toHaveValue("Example123");
  await page.getByRole("button", { name: "회원가입", exact: true }).click();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(
    "다시 만나 반가워요",
  );
  await page
    .getByLabel("이메일", { exact: true })
    .fill("language@example.test");
  await page.getByLabel("비밀번호", { exact: true }).fill("Example123");
  await page.getByRole("button", { name: "로그인", exact: true }).click();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(
    "테스트 이름님, 안녕하세요.",
  );
  await switchTo(page, "en");
  await expect(page.getByText("No upcoming appointments")).toBeVisible();
  await page
    .getByRole("banner")
    .getByRole("button", { name: "Log out" })
    .click();
  await switchTo(page, "ko");
  await page.reload();
  await expect(language(page)).toHaveValue("ko");
  const second = await context.newPage();
  await second.goto("/#/login");
  await expect(second.getByRole("heading", { level: 1 })).toHaveText(
    "다시 만나 반가워요",
  );
  await second.close();
  await page.evaluate(() =>
    localStorage.setItem("visit-notes-language", "invalid"),
  );
  await page.reload();
  await expect(language(page)).toHaveValue("en");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(
    "Welcome back",
  );
  await noMissing(page);
});

for (const width of [360, 1440])
  test(`guest questionnaire, unchanged data and bilingual completion ${width}`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 900 });
    await page.goto("/");
    await expect(page.getByRole("heading", { level: 1 })).toHaveText(
      "Before your visit, put your story into words.",
    );
    await noOverflow(page);
    await page
      .getByRole("button", { name: "Start questionnaire", exact: false })
      .click();
    await page
      .getByLabel("Main reason for your visit")
      .fill("My symptoms — 내 이야기");
    const before = await snapshot(page);
    await switchTo(page, "ko");
    expect(await snapshot(page)).toEqual(before);
    await expect(page.getByLabel("가장 먼저 이야기할 문제")).toHaveValue(
      "My symptoms — 내 이야기",
    );
    await switchTo(page, "en");
    await next(page);
    await page.getByRole("radio", { name: "Today", exact: true }).check();
    await next(page);
    await page
      .getByRole("radio", { name: "They come and go", exact: true })
      .check();
    await next(page);
    await expect(page.getByRole("heading", { level: 1 })).toHaveText(
      "How often do they come and go?",
    );
    const branching = await snapshot(page);
    await switchTo(page, "ko");
    expect(await snapshot(page)).toEqual(branching);
    await switchTo(page, "en");
    await page
      .getByRole("radio", { name: "Several times a day", exact: true })
      .check();
    await next(page);
    // A typed answer that happens to equal a Korean option is still patient text.
    await page.getByLabel("Describe in your own words").fill("보통이에요");
    await switchTo(page, "ko");
    await expect(page.getByLabel("내 말로 설명하기")).toHaveValue("보통이에요");
    await switchTo(page, "en");
    await next(page);
    for (let i = 0; i < 5; i++) {
      await page
        .getByRole("button", {
          name: i === 0 ? "None" : "Not sure",
          exact: true,
        })
        .click();
      if (i === 4) {
        await page.getByText("Demo controls", { exact: true }).click();
        await page.getByRole("button", { name: "Fail next response" }).click();
      }
      await next(page);
    }
    await expect(page.getByRole("alert")).toContainText(
      "The demo response failed.",
    );
    await switchTo(page, "ko");
    await expect(page.getByRole("alert")).toContainText(
      "데모 응답을 받지 못했어요.",
    );
    await switchTo(page, "en");
    await next(page);
    await expect(page.getByRole("heading", { level: 1 })).toHaveText(
      "Review your notes before your visit.",
    );
    await expect(page.locator(".summary")).toContainText("Started: Today");
    await expect(page.locator(".summary")).toContainText(
      "Discomfort: 보통이에요",
    );
    await page.getByRole("checkbox").check();
    const approved = await snapshot(page);
    await switchTo(page, "ko");
    expect(await snapshot(page)).toEqual(approved);
    await expect(page.getByRole("checkbox")).toBeChecked();
    await noOverflow(page);
    await page.screenshot({
      path: `test-results/screenshots/i18n-${width}-ko-review.png`,
      fullPage: true,
    });
    await switchTo(page, "en");
    await noOverflow(page);
    await page.screenshot({
      path: `test-results/screenshots/i18n-${width}-en-review.png`,
      fullPage: true,
    });
    const axe = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
      .analyze();
    expect(axe.violations).toEqual([]);
    await page
      .getByRole("button", { name: /Confirm and simulate handoff/ })
      .click();
    await expect(page.getByRole("heading", { level: 1 })).toHaveText(
      "Handoff simulation complete",
    );
    const downloadEvent = page.waitForEvent("download");
    await page.getByRole("button", { name: /Download summary text/ }).click();
    const download = await downloadEvent;
    expect(await readFile(await download.path(), "utf8")).toContain(
      "Visit Notes — Demo summary",
    );
    await switchTo(page, "ko");
    await expect(page.getByRole("heading", { level: 1 })).toHaveText(
      "전달 시뮬레이션 완료",
    );
    await page.reload();
    await expect(language(page)).toHaveValue("ko");
    await noMissing(page);
  });

for (const width of [360, 1440])
  test(`account routes, filters, storage and read-only records ${width}`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 900 });
    await login(page);
    await noOverflow(page);
    await page
      .getByRole("navigation")
      .getByRole("link", { name: "Appointments", exact: true })
      .click();
    await page.getByRole("button", { name: "Past", exact: true }).click();
    const before = await snapshot(page);
    await switchTo(page, "ko");
    expect(await snapshot(page)).toEqual(before);
    await expect(
      page.getByRole("button", { name: "지난 예약", exact: true }),
    ).toHaveAttribute("aria-pressed", "true");
    await switchTo(page, "en");
    await page.getByRole("button", { name: "Upcoming", exact: true }).click();
    await page.locator('a[href="#/appointments/apt-a-next"]').click();
    const date = await page.locator(".detail-facts dd").first().innerText();
    await switchTo(page, "ko");
    expect(
      await page.locator(".detail-facts dd").first().innerText(),
    ).not.toEqual(date);
    await expect(page).toHaveTitle(/진료노트/);
    await switchTo(page, "en");
    await expect(page).toHaveTitle(/Visit Notes/);
    await page.getByRole("link", { name: /^Continue writing/ }).click();
    await expect(page.getByRole("heading", { level: 1 })).toHaveText(
      "How have your symptoms changed?",
    );
    await page
      .getByLabel("Describe in your own words")
      .fill("Still uncomfortable / 그대로");
    const editing = await snapshot(page);
    await switchTo(page, "ko");
    expect(await snapshot(page)).toEqual(editing);
    await expect(page.getByLabel("내 말로 설명하기")).toHaveValue(
      "Still uncomfortable / 그대로",
    );
    await switchTo(page, "en");
    await page.getByRole("button", { name: /Save and go to my notes/ }).click();
    await page.getByRole("button", { name: "Sent", exact: true }).click();
    await switchTo(page, "ko");
    await expect(
      page.getByRole("button", { name: "전달 완료", exact: true }),
    ).toHaveAttribute("aria-pressed", "true");
    await switchTo(page, "en");
    await page.getByRole("link", { name: /^View note/ }).click();
    const sent = await snapshot(page);
    await switchTo(page, "ko");
    expect(await snapshot(page)).toEqual(sent);
    await switchTo(page, "en");
    await expect(page.getByText("Record at handoff · Read only")).toBeVisible();
    await noOverflow(page);
    await page
      .getByRole("navigation")
      .getByRole("link", { name: "Account", exact: true })
      .click();
    await switchTo(page, "ko");
    await expect(page.getByRole("heading", { level: 1 })).toHaveText(
      "계정 정보",
    );
    await switchTo(page, "en");
    await page
      .getByRole("navigation")
      .getByRole("link", { name: "My home", exact: true })
      .click();
    await page.getByText("Demo controls", { exact: true }).click();
    await page.getByRole("button", { name: "Simulate load failure" }).click();
    await expect(page.getByRole("alert")).toContainText(
      "The demo request failed.",
    );
    await expect(page).toHaveTitle("Unable to load information · Visit Notes");
    await switchTo(page, "ko");
    await expect(page.getByRole("alert")).toContainText(
      "데모 요청을 처리하지 못했어요.",
    );
    await expect(page).toHaveTitle("정보를 불러오지 못했어요 · 진료노트");
    await switchTo(page, "en");
    await page.getByRole("button", { name: "Try again" }).click();
    await expect(page.getByRole("heading", { level: 1 })).toContainText(
      "Hello",
    );
    await page.getByText("Demo controls", { exact: true }).click();
    await page.getByRole("button", { name: "Simulate slow loading" }).click();
    await expect(page.getByRole("status")).toContainText(
      "Loading demo information.",
    );
    await switchTo(page, "ko");
    await expect(page.getByRole("status")).toContainText(
      "데모 정보를 확인하고 있어요.",
    );
    await expect(page.getByRole("heading", { level: 1 })).toContainText(
      "안녕하세요",
    );
    await noOverflow(page);
    await page.screenshot({
      path: `test-results/screenshots/i18n-${width}-ko-home.png`,
      fullPage: true,
    });
    await switchTo(page, "en");
    await page.screenshot({
      path: `test-results/screenshots/i18n-${width}-en-home.png`,
      fullPage: true,
    });
    await page.getByText("Demo controls", { exact: true }).click();
    await page.getByRole("button", { name: "Simulate session expiry" }).click();
    await expect(
      page.getByText("Your session has expired. Please log in again."),
    ).toBeVisible();
    await switchTo(page, "ko");
    await expect(
      page.getByText("세션이 만료되었어요. 다시 로그인해 주세요."),
    ).toBeVisible();
    await noMissing(page);
  });

test("unavailable localStorage keeps a usable in-memory language choice", async ({
  page,
}) => {
  await page.addInitScript(() =>
    Object.defineProperty(window, "localStorage", {
      get() {
        throw new Error("blocked");
      },
    }),
  );
  await page.goto("/#/login");
  await switchTo(page, "ko");
  await expect(
    page.getByText(
      "이번 방문에는 선택한 언어가 적용됩니다. 브라우저 저장소를 사용할 수 없습니다.",
    ),
  ).toBeVisible();
  await page.getByRole("link", { name: "회원가입", exact: true }).click();
  await expect(language(page)).toHaveValue("ko");
  await noMissing(page);
});

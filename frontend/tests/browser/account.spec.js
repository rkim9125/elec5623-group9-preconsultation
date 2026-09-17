import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
test.setTimeout(60000);
test.beforeEach(async ({ page }) => {
  await page.addInitScript(() =>
    localStorage.setItem("visit-notes-language", "ko"),
  );
});
async function login(page, name = "데모 가람") {
  await page.getByRole("button", { name: new RegExp(name) }).click();
  await page.getByRole("button", { name: "로그인", exact: true }).click();
}
async function open(page, path) {
  await page.goto(`/#${path}`);
}
async function logout(page) {
  await page
    .getByRole("banner")
    .getByRole("button", { name: "로그아웃", exact: true })
    .click();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(
    "다시 만나 반가워요",
  );
}
async function shot(page, name) {
  await page.evaluate(async () => {
    await document.fonts.ready;
    await Promise.all(document.getAnimations().map((a) => a.finished));
  });
  await page.screenshot({
    path: `test-results/screenshots/account-${name}.png`,
    fullPage: true,
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
}
async function navigate(page, name) {
  await page
    .getByRole("navigation", { name: "환자 계정 메뉴" })
    .getByRole("link", { name, exact: true })
    .click();
}
for (const width of [360, 1440])
  test(`account home, appointments, editor, immutable sent snapshot ${width}`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 900 });
    const errors = [];
    page.on("pageerror", (e) => errors.push(e.message));
    await open(page, "/login");
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    await shot(page, `${width}-login`);
    await login(page);
    await expect(page.getByRole("heading", { level: 1 })).toContainText(
      "데모 가람",
    );
    await shot(page, `${width}-home`);
    const axe = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
      .analyze();
    expect(axe.violations).toEqual([]);
    await navigate(page, "예약 현황");
    await expect(page.locator(".list-count")).toHaveText("2개의 예약");
    await shot(page, `${width}-appointments`);
    await page.getByRole("button", { name: "지난 예약", exact: true }).click();
    await expect(page.locator(".appointment-row")).toContainText("예약 확정");
    await page.getByRole("button", { name: "취소", exact: true }).click();
    await page.locator(".appointment-row").click();
    await expect(page.getByRole("button", { name: /문진 작성/ })).toHaveCount(
      0,
    );
    await open(page, "/appointments/apt-a-new");
    await page.getByRole("button", { name: /문진 작성/ }).click();
    await expect(page.getByRole("heading", { level: 1 })).toHaveText(
      "어떤 이유로 방문하시나요?",
    );
    await page
      .getByLabel("가장 먼저 이야기할 문제")
      .fill("가상 예약에 연결한 새 문진");
    await page.getByRole("button", { name: /^계속/ }).click();
    await page.getByRole("button", { name: "저장하고 내 문진으로 →" }).click();
    await expect(page.locator(".record-list")).toContainText(
      "가상 예약에 연결한 새 문진",
    );
    await open(page, "/appointments/apt-a-new");
    await expect(page.getByRole("link", { name: "이어서 작성 →" })).toHaveCount(
      1,
    );
    await page.getByRole("link", { name: "이어서 작성 →" }).click();
    await expect(page.getByRole("heading", { level: 1 })).toHaveText(
      "언제부터 불편하셨나요?",
    );
    await page.getByRole("button", { name: "저장하고 내 문진으로 →" }).click();
    await expect(
      page
        .locator(".intake-row")
        .filter({ hasText: "가상 예약에 연결한 새 문진" }),
    ).toHaveCount(1);
    await open(page, "/intakes/intake-a-ready");
    await page.getByRole("link", { name: /요약 검토·수정/ }).click();
    await expect(page.getByRole("checkbox")).toBeChecked();
    await page
      .getByRole("button", { name: "관련 병력 수정", exact: true })
      .click();
    await page.getByRole("textbox").fill("계정에서 수정한 가상 병력");
    await page.getByRole("button", { name: /수정하고 요약으로/ }).click();
    await expect(page.getByRole("checkbox")).not.toBeChecked();
    await expect(
      page.getByRole("button", { name: /확인하고 전달/ }),
    ).toBeDisabled();
    await page.getByRole("checkbox").check();
    await page.getByRole("button", { name: /확인하고 전달/ }).click();
    await expect(page.getByText("전달 당시의 기록 · 읽기 전용")).toBeVisible();
    await expect(page.locator(".summary")).toContainText(
      "계정에서 수정한 가상 병력",
    );
    await shot(page, `${width}-sent`);
    await open(page, "/intakes/intake-a-ready/edit/review");
    await expect(page.getByText("전달 당시의 기록 · 읽기 전용")).toBeVisible();
    await expect(page.getByRole("checkbox")).toHaveCount(0);
    await expect(
      page.getByRole("button", { name: "관련 병력 수정", exact: true }),
    ).toHaveCount(0);
    await navigate(page, "내 문진");
    await page.getByRole("button", { name: "전달 완료", exact: true }).click();
    await expect(page.locator(".list-count")).toHaveText("2개의 문진");
    await shot(page, `${width}-intakes`);
    expect(errors).toEqual([]);
  });
test("signup validation, login errors, empty state, logout and safe return", async ({
  page,
}) => {
  await open(page, "/signup");
  await page.getByRole("button", { name: "회원가입", exact: true }).click();
  await expect(page.getByLabel("이름", { exact: true })).toBeFocused();
  await page.getByLabel("이름", { exact: true }).fill("가상 새환자");
  await page.getByLabel("이메일", { exact: true }).fill("new@example.test");
  await page.getByLabel("비밀번호", { exact: true }).fill("Example1234");
  await page.getByLabel("비밀번호 확인", { exact: true }).fill("different");
  await page.getByRole("button", { name: "회원가입", exact: true }).click();
  await expect(
    page.getByText("비밀번호가 일치하지 않습니다. 다시 확인해 주세요."),
  ).toBeVisible();
  await page.getByLabel("비밀번호 확인", { exact: true }).fill("Example1234");
  await page
    .getByRole("button", { name: "회원가입", exact: true })
    .evaluate((e) => {
      e.click();
      e.click();
    });
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(
    "다시 만나 반가워요",
  );
  await page.getByLabel("이메일", { exact: true }).fill("new@example.test");
  await page.getByLabel("비밀번호", { exact: true }).fill("wrong");
  await page.getByRole("button", { name: "로그인", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("이메일 또는 비밀번호");
  await expect(page.getByLabel("이메일", { exact: true })).toHaveValue(
    "new@example.test",
  );
  await page.getByLabel("비밀번호", { exact: true }).fill("Example1234");
  await page.getByRole("button", { name: "로그인", exact: true }).click();
  await expect(page.getByRole("heading", { level: 1 })).toContainText(
    "가상 새환자",
  );
  await expect(page.getByText("예정된 예약이 없어요")).toBeVisible();
  expect(
    await page.evaluate(() =>
      JSON.stringify({ ...sessionStorage, ...localStorage }).includes(
        "Example1234",
      ),
    ),
  ).toBe(false);
  await navigate(page, "계정 정보");
  await logout(page);
  await page.goBack();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(
    "다시 만나 반가워요",
  );
  await open(page, "/login?returnTo=https%3A%2F%2Fevil.test");
  await login(page, "데모 새봄");
  await expect(page).toHaveURL(/#\/my$/);
  await navigate(page, "내 문진");
  await expect(page.getByText("아직 작성한 문진이 없어요")).toBeVisible();
});
test("deep return, cross-account ownership, stale loads, missing IDs, expiry and retry", async ({
  page,
}) => {
  await open(page, "/appointments/apt-a-next");
  await expect(page).toHaveURL(/login\?returnTo=/);
  await login(page);
  await expect(page).toHaveURL(/#\/appointments\/apt-a-next$/);
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(
    "가상 온유의원",
  );
  await navigate(page, "내 문진");
  await page.getByText("데모 테스트", { exact: true }).click();
  await page.getByRole("button", { name: "조회 실패 체험" }).click();
  await expect(page.getByRole("alert")).toContainText(
    "정보를 불러오지 못했어요",
  );
  await page.getByRole("button", { name: "다시 시도", exact: true }).click();
  await expect(page.locator(".intake-row")).toHaveCount(3);
  await page.getByText("데모 테스트", { exact: true }).click();
  await page.getByRole("button", { name: "느린 조회 체험" }).click();
  await expect(page.locator(".account-loading")).toContainText(
    "데모 정보를 확인",
  );
  await logout(page);
  await login(page, "데모 나래");
  await expect(page.getByRole("heading", { level: 1 })).toContainText(
    "데모 나래",
  );
  await page.waitForTimeout(1900);
  await expect(page.locator("body")).not.toContainText("가상 온유의원");
  await open(page, "/intakes/intake-a-ready");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(
    "기록을 찾을 수 없어요",
  );
  await open(page, "/appointments/apt-a-next");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(
    "기록을 찾을 수 없어요",
  );
  await open(page, "/intakes/no-such-id");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(
    "기록을 찾을 수 없어요",
  );
  await navigate(page, "내 문진");
  await page.getByRole("button", { name: "전달 완료", exact: true }).click();
  await expect(page.getByText("이 상태의 문진이 없어요")).toBeVisible();
  await page.getByText("데모 테스트", { exact: true }).click();
  await page.getByRole("button", { name: "세션 만료 체험" }).click();
  await expect(
    page.getByText("세션이 만료되었어요. 다시 로그인해 주세요."),
  ).toBeVisible();
  await login(page, "데모 나래");
  await expect(page).toHaveURL(/#\/intakes$/);
});
test("guest import is opt-in, editor reload preserves owned state, keyboard login", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByRole("button", { name: "가상 예시로 체험하기 ↗" }).click();
  await page.getByLabel("가장 먼저 이야기할 문제").fill("가상 비로그인 문진");
  await page.getByRole("link", { name: "로그인 · 내 진료노트 →" }).click();
  await page.getByLabel("이메일", { exact: true }).focus();
  await page.keyboard.type("empty@example.test");
  await page.keyboard.press("Tab");
  await page.keyboard.type("Demo1234!");
  await page.keyboard.press("Enter");
  await expect(page.getByRole("heading", { level: 1 })).toContainText(
    "데모 새봄",
  );
  await expect(
    page.getByText(
      "아직 작성한 문진이 없습니다. 첫 문진을 작성하면 여기에 표시돼요.",
    ),
  ).toBeVisible();
  await page.getByRole("button", { name: "내 계정으로 가져오기" }).focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(
    "가상 비로그인 문진",
  );
  await page.getByRole("link", { name: "이어서 작성 →" }).click();
  await page
    .getByLabel("가장 먼저 이야기할 문제")
    .fill("계정에 보관한 가상 문진");
  await page.getByRole("button", { name: /^계속/ }).click();
  await page.reload();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(
    "언제부터 불편하셨나요?",
  );
  await page.getByRole("button", { name: "저장하고 내 문진으로 →" }).click();
  await expect(page.locator(".intake-row")).toHaveCount(1);
  await expect(page.locator(".intake-row")).toContainText(
    "계정에 보관한 가상 문진",
  );
  await expect(page.getByRole("heading", { level: 1 })).toBeFocused();
});

async function tabTo(page, text) {
  for (let i = 0; i < 90; i++) {
    const active = await page.evaluate(
      () => document.activeElement?.textContent?.trim() || "",
    );
    if (active === text || active.endsWith(text)) {
      await page.keyboard.press("Enter");
      return;
    }
    await page.keyboard.press("Tab");
  }
  throw new Error(`키보드로 찾지 못한 항목: ${text}`);
}
test("keyboard account navigation, signup failure and account reset", async ({
  page,
}) => {
  await page.setViewportSize({ width: 360, height: 800 });
  await open(page, "/signup");
  await page.getByLabel("이름", { exact: true }).fill("가상 가입자");
  await page.getByLabel("이메일", { exact: true }).fill("failure@example.test");
  await page.getByLabel("비밀번호", { exact: true }).fill("Example1234");
  await page.getByLabel("비밀번호 확인", { exact: true }).fill("Example1234");
  await page.getByText("데모 테스트", { exact: true }).click();
  await page.getByRole("button", { name: "다음 인증 요청 실패" }).click();
  await page.getByRole("button", { name: "회원가입", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("다시 시도");
  await expect(page.getByLabel("이메일", { exact: true })).toHaveValue(
    "failure@example.test",
  );
  await open(page, "/login");
  await expect(page.getByRole("heading", { level: 1 })).toBeFocused();
  await page.keyboard.press("Tab");
  await page.keyboard.type("narae@example.test");
  await page.keyboard.press("Tab");
  await page.keyboard.type("Demo1234!");
  await page.keyboard.press("Enter");
  await expect(page.getByRole("heading", { level: 1 })).toContainText(
    "데모 나래",
  );
  await tabTo(page, "계정 정보");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("계정 정보");
  await shot(page, "360-profile");
  await tabTo(page, "데모 기록 초기화");
  await page.getByRole("button", { name: "기록 초기화 확인" }).click();
  await navigate(page, "예약 현황");
  await expect(page.getByText("등록된 예약이 없어요")).toBeVisible();
  await page.reload();
  await expect(page.getByText("등록된 예약이 없어요")).toBeVisible();
  await tabTo(page, "로그아웃");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(
    "다시 만나 반가워요",
  );
  await login(page, "데모 가람");
  await expect(page.getByRole("heading", { level: 1 })).toContainText(
    "데모 가람",
  );
  await expect(page.locator(".home-next")).toContainText("가상 온유의원");
});

test("blank additional reason cannot bypass review via return button", async ({
  page,
}) => {
  await open(page, "/login");
  await login(page);
  await expect(page.getByRole("heading", { level: 1 })).toContainText(
    "데모 가람",
  );
  await open(page, "/intakes/intake-a-ready/edit/review");
  await page
    .getByRole("button", { name: "방문 목적 수정", exact: true })
    .click();
  await page.getByRole("button", { name: "＋ 다른 문제 추가" }).click();
  await page.getByRole("button", { name: "요약으로", exact: true }).click();
  await expect(
    page.getByText("방문 이유에 비어 있는 항목이 있어요"),
  ).toBeVisible();
  await page.getByRole("checkbox").check();
  await expect(
    page.getByRole("button", { name: /확인하고 전달/ }),
  ).toBeDisabled();
  await page.getByRole("button", { name: "방문 이유 확인 →" }).click();
  await page.getByRole("button", { name: "삭제", exact: true }).click();
  await page.getByRole("button", { name: /수정하고 요약으로/ }).click();
  await expect(page.getByRole("checkbox")).not.toBeChecked();
  await page.getByRole("checkbox").check();
  await expect(
    page.getByRole("button", { name: /확인하고 전달/ }),
  ).toBeEnabled();
});

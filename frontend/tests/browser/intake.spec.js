import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
const goNext = (page) => page.getByRole("button", { name: /^계속/ }).click();
async function start(page) {
  await page.goto("/");
  await page.getByRole("button", { name: "가상 예시로 체험하기 ↗" }).click();
  await goNext(page);
}
async function fillFlow(page) {
  await start(page);
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(
    "증상이 어떻게 변하고 있나요?",
  );
  await page.evaluate(async () => {
    await document.fonts.ready;
    await Promise.all(document.getAnimations().map((a) => a.finished));
  });
  await page.screenshot({
    path: `../docs/screenshots/${page.viewportSize().width}-question.png`,
    fullPage: true,
  });
  await page.getByRole("radio", { name: "반복돼요", exact: true }).check();
  await goNext(page);
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(
    "얼마나 자주 반복되나요?",
  );
  await page
    .getByRole("radio", { name: "하루에 여러 번", exact: true })
    .check();
  await goNext(page);
  await page.getByRole("radio", { name: "보통이에요", exact: true }).check();
  await goNext(page);
  await page.getByRole("button", { name: "없음", exact: true }).click();
  await goNext(page);
  await page.getByRole("button", { name: "모름", exact: true }).click();
  await goNext(page);
  await page.getByRole("radio", { name: "있어요 · 직접 입력" }).check();
  await page.getByLabel("약 이름").fill("가상 약 A");
  await page.getByLabel("용량·복용 방법").fill("용량 모름, 하루 한 번");
  await page.getByRole("button", { name: "＋ 복용약 추가" }).click();
  await page.getByLabel("약 이름").nth(1).fill("삭제할 약");
  await page.getByRole("button", { name: "2번 항목 삭제" }).click();
  await page.getByLabel("약 이름").fill("가상 약 B");
  await goNext(page);
  await page.getByRole("radio", { name: "있어요 · 직접 입력" }).check();
  await page.getByLabel("알레르기 원인").fill("가상 원인 A");
  await page.getByLabel("경험한 반응").fill("가려움");
  await page.getByRole("button", { name: "＋ 알레르기 추가" }).click();
  await page.getByRole("button", { name: "2번 항목 삭제" }).click();
  await page.getByLabel("알레르기 원인").fill("가상 원인 B");
  await goNext(page);
  await goNext(page);
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(
    "진료 전에 한 번 확인해 주세요.",
  );
}
for (const width of [360, 1440])
  test(`complete flow, editing, failures and screenshots ${width}px`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: width === 360 ? 800 : 1000 });
    const errors = [];
    page.on("pageerror", (e) => errors.push(e.message));
    await page.goto("/");
    await page.evaluate(async () => {
      await document.fonts.ready;
      await Promise.all(document.getAnimations().map((a) => a.finished));
    });
    await page.screenshot({
      path: `../docs/screenshots/${width}-start.png`,
      fullPage: true,
    });
    await fillFlow(page);
    await expect(page.locator(".summary")).toContainText("일상 영향: 없음");
    await expect(page.locator(".summary")).toContainText("관련 병력");
    await expect(page.locator(".summary")).toContainText("모름");
    await expect(page.locator(".summary")).toContainText("미응답");
    await expect(page.locator(".summary")).toContainText("가상 약 B");
    await expect(page.locator(".summary")).not.toContainText("삭제할 약");
    await expect(page.locator(".summary")).toContainText("가상 원인 B");
    await page.getByRole("checkbox").check();
    await page
      .getByRole("button", { name: "증상의 경과 수정", exact: true })
      .click();
    await page.getByRole("radio", { name: "비슷해요", exact: true }).check();
    await page.getByRole("button", { name: /수정하고 요약으로/ }).click();
    await expect(page.getByRole("checkbox")).not.toBeChecked();
    await expect(page.locator(".summary")).not.toContainText("빈도:");
    await expect(
      page.getByRole("button", { name: /확인하고 전달/ }),
    ).toBeDisabled();
    await page
      .getByRole("button", { name: "증상의 경과 수정", exact: true })
      .click();
    await page.getByRole("radio", { name: "반복돼요", exact: true }).check();
    await page.getByRole("button", { name: /수정하고 요약으로/ }).click();
    await expect(page.getByRole("heading", { level: 1 })).toHaveText(
      "얼마나 자주 반복되나요?",
    );
    await expect(
      page.getByRole("radio", { name: "하루에 여러 번", exact: true }),
    ).not.toBeChecked();
    await page.getByRole("button", { name: "모름", exact: true }).click();
    await page.getByRole("button", { name: /수정하고 요약으로/ }).click();
    await expect(page.locator(".summary")).toContainText("빈도: 모름");
    await page.reload();
    await expect(page.locator(".summary")).toContainText("빈도: 모름");
    await page.evaluate(async () => {
      await document.fonts.ready;
      await Promise.all(document.getAnimations().map((a) => a.finished));
    });
    await page.screenshot({
      path: `../docs/screenshots/${width}-review.png`,
      fullPage: true,
    });
    const accessibility = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
      .analyze();
    expect(accessibility.violations).toEqual([]);
    await page.getByRole("checkbox").check();
    await page.getByText("데모 테스트", { exact: true }).click();
    await page.getByRole("button", { name: "다음 응답 실패시키기" }).click();
    await page.getByText("데모 테스트", { exact: true }).click();
    await page.getByRole("button", { name: /확인하고 전달/ }).click();
    await expect(page.getByRole("alert")).toContainText("다시 시도");
    await expect(page.locator(".summary")).toContainText("가상 약 B");
    await page.getByRole("button", { name: /확인하고 전달/ }).evaluate((el) => {
      el.click();
      el.click();
    });
    await expect(page.getByRole("heading", { level: 1 })).toHaveText(
      "전달 시뮬레이션 완료",
    );
    await expect(page.getByRole("heading", { level: 1 })).toBeFocused();
    await page.evaluate(async () => {
      await document.fonts.ready;
      await Promise.all(document.getAnimations().map((a) => a.finished));
    });
    await page.screenshot({
      path: `../docs/screenshots/${width}-done.png`,
      fullPage: true,
    });
    const download = page.waitForEvent("download");
    await page.getByRole("button", { name: /요약 텍스트 다운로드/ }).click();
    expect((await download).suggestedFilename()).toContain("요약.txt");
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    expect(errors).toEqual([]);
  });
test("keyboard errors, browser history, storage, long input and stale responses", async ({
  page,
}) => {
  await page.setViewportSize({ width: 360, height: 800 });
  await page.goto("/");
  await page.getByRole("button", { name: "문진 시작" }).focus();
  await page.keyboard.press("Enter");
  await goNext(page);
  await expect(page.getByLabel("가장 먼저 이야기할 문제")).toBeFocused();
  await expect(page.getByRole("alert")).toContainText("방문 이유");
  await page
    .getByLabel("가장 먼저 이야기할 문제")
    .fill("가상 증상 ".repeat(450));
  await page.evaluate(async () => {
    await document.fonts.ready;
    await Promise.all(document.getAnimations().map((a) => a.finished));
  });
  await page.screenshot({
    path: "../docs/screenshots/360-reason.png",
    fullPage: true,
  });
  await goNext(page);
  await expect(page.getByRole("heading", { level: 1 })).toBeFocused();
  await page.goBack();
  await expect(page.getByLabel("가장 먼저 이야기할 문제")).toHaveValue(
    "가상 증상 ".repeat(450),
  );
  await page.reload();
  await expect(page.getByLabel("가장 먼저 이야기할 문제")).toHaveValue(
    "가상 증상 ".repeat(450),
  );
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.getByRole("button", { name: "데모 데이터 초기화" }).click();
  await page.getByRole("button", { name: "초기화", exact: true }).click();
  await fillFlow(page);
  await page.getByRole("checkbox").check();
  await page.getByRole("button", { name: /확인하고 전달/ }).click();
  await page
    .getByRole("button", { name: "관련 병력 수정", exact: true })
    .click();
  await page.getByRole("textbox").fill("최신 병력");
  await page.waitForTimeout(800);
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(
    "관련해서 알리고 싶은 병력이 있나요?",
  );
  await page.getByRole("button", { name: /수정하고 요약으로/ }).click();
  await expect(page.locator(".summary")).toContainText("최신 병력");
  await expect(page.getByRole("checkbox")).not.toBeChecked();
});

async function keyboardTo(page, name, key = "Enter") {
  for (let i = 0; i < 90; i++) {
    const current = await page.evaluate(() => {
      const e = document.activeElement;
      return e?.getAttribute("aria-label") || e?.textContent?.trim() || "";
    });
    if (current === name || current.startsWith(name)) {
      await page.keyboard.press(key);
      return;
    }
    await page.keyboard.press("Tab");
  }
  throw new Error(`Keyboard target not reachable: ${name}`);
}

test("keyboard-only journey, summary failure, and editing refresh", async ({
  page,
}) => {
  await page.goto("/");
  await keyboardTo(page, "문진 시작");
  await page.keyboard.press("Tab");
  await page.keyboard.type("가상 방문 이유");
  await keyboardTo(page, "계속");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(
    "언제부터 불편하셨나요?",
  );
  for (const title of [
    "언제부터 불편하셨나요?",
    "증상이 어떻게 변하고 있나요?",
    "얼마나 불편하신가요?",
    "일상에서 어떤 점이 어려운가요?",
    "관련해서 알리고 싶은 병력이 있나요?",
    "현재 복용하는 약이 있나요?",
    "알고 있는 알레르기가 있나요?",
  ]) {
    await expect(page.getByRole("heading", { level: 1 })).toHaveText(title);
    await keyboardTo(page, "모름");
    await keyboardTo(page, "계속");
  }
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(
    "의사에게 무엇을 묻고 싶으신가요?",
  );
  await keyboardTo(page, "데모 테스트");
  await keyboardTo(page, "다음 응답 실패시키기");
  await keyboardTo(page, "계속");
  await expect(page.getByRole("alert")).toContainText("다시 시도");
  await keyboardTo(page, "계속");
  await expect(page.locator(".summary")).toBeVisible();
  await keyboardTo(page, "관련 병력 수정");
  await page.reload();
  await expect(
    page.getByRole("button", { name: /수정하고 요약으로/ }),
  ).toBeVisible();
  await keyboardTo(page, "없음");
  await keyboardTo(page, "수정하고 요약으로");
  await expect(page.locator(".summary")).toBeVisible();
  // The checkbox is immediately after the last section edit control in tab order.
  for (let i = 0; i < 60; i++) {
    if (
      await page
        .getByRole("checkbox")
        .evaluate((e) => e === document.activeElement)
    )
      break;
    await page.keyboard.press("Tab");
  }
  await page.keyboard.press("Space");
  await expect(page.getByRole("checkbox")).toBeChecked();
  await keyboardTo(page, "확인하고 전달 시뮬레이션");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(
    "전달 시뮬레이션 완료",
  );
});

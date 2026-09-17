import { summary } from "../model.js";
// Replace these Promise-based methods with an API adapter; no network requests.
export function createMockService(delay = 650) {
  let failNext = false;
  return {
    failOnce() {
      failNext = true;
    },
    async request(kind, data) {
      const fail = failNext;
      failNext = false;
      const snapshot = structuredClone(data);
      await new Promise((resolve) => setTimeout(resolve, delay));
      if (fail)
        throw new Error(
          "데모 응답을 받지 못했어요. 입력은 그대로 보관되어 있습니다. 다시 시도해 주세요.",
        );
      return { revision: snapshot.revision, sections: summary(snapshot), kind };
    },
  };
}
export const mock = createMockService();

// Only copy an explicit leading phrase. No inferred dates or medical interpretation.
export function extractExplicitOnset(text) {
  const match = text
    .trim()
    .match(/^(오늘부터|며칠 전부터|일주일 전부터|한 달 전부터)(?=\s)/);
  return match ? match[1] : null;
}

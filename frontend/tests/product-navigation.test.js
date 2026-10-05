import test from "node:test";
import assert from "node:assert/strict";
import {
  navigateWithGuard,
  registerNavigationGuard,
} from "../src/product/navigation.js";

test("navigation waits for the last draft to persist before leaving", async () => {
  let release;
  const saved = new Promise((resolve) => {
    release = resolve;
  });
  const calls = [];
  const remove = registerNavigationGuard(async () => {
    calls.push("save");
    await saved;
    return true;
  });
  const navigation = navigateWithGuard(() => calls.push("leave"));
  assert.deepEqual(calls, ["save"]);
  release();
  assert.equal(await navigation, true);
  assert.deepEqual(calls, ["save", "leave"]);
  remove();
});

test("a failed draft save blocks navigation and preserves the screen", async () => {
  let left = false;
  const remove = registerNavigationGuard(async () => false);
  assert.equal(
    await navigateWithGuard(() => {
      left = true;
    }),
    false,
  );
  assert.equal(left, false);
  remove();
});

test("only the latest requested destination is used after an in-flight save", async () => {
  let release;
  const pending = new Promise((resolve) => {
    release = resolve;
  });
  const visited = [];
  const remove = registerNavigationGuard(async () => {
    await pending;
    return true;
  });
  const first = navigateWithGuard(() => visited.push("history"));
  const second = navigateWithGuard(() => visited.push("overview"));
  release();
  assert.deepEqual(await Promise.all([first, second]), [false, true]);
  assert.deepEqual(visited, ["overview"]);
  remove();
});

test("unmounting an older form cannot remove a newer form's save boundary", async () => {
  const old = registerNavigationGuard(async () => true);
  const current = registerNavigationGuard(async () => false);
  old();
  assert.equal(
    await navigateWithGuard(() => assert.fail("must stay on current form")),
    false,
  );
  current();
  assert.equal(await navigateWithGuard(() => {}), true);
});

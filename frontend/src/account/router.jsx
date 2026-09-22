import { useSyncExternalStore } from "react";
let accepted = location.hash.slice(1) || "start";
let blocker = null;
const listeners = new Set();
const emit = () => listeners.forEach((fn) => fn());
export function setRouteBlocker(fn) {
  blocker = fn;
  return () => {
    if (blocker === fn) blocker = null;
  };
}
export function go(path, { replace = false, bypass = false, onNavigate } = {}) {
  if (
    path !== accepted &&
    !bypass &&
    blocker?.(() => go(path, { replace, bypass: true, onNavigate }))
  )
    return;
  history[replace ? "replaceState" : "pushState"](null, "", `#${path}`);
  accepted = path;
  onNavigate?.();
  emit();
}
function nativeNavigation() {
  const path = location.hash.slice(1) || "start";
  if (path === accepted) {
    emit();
    return;
  }
  if (blocker?.(() => go(path, { replace: true, bypass: true }))) {
    history.replaceState(null, "", `#${accepted}`);
    return;
  }
  accepted = path;
  emit();
}
window.addEventListener("popstate", nativeNavigation);
window.addEventListener("hashchange", nativeNavigation);
function subscribe(fn) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}
export function useRoute() {
  return useSyncExternalStore(
    subscribe,
    () => location.hash.slice(1) || "start",
  );
}
export function RouteLink({ to, children, ...props }) {
  return (
    <a
      {...props}
      href={`#${to}`}
      onClick={(e) => {
        if (!e.ctrlKey && !e.metaKey && !e.shiftKey && e.button === 0) {
          e.preventDefault();
          go(to);
        }
      }}
    >
      {children}
    </a>
  );
}

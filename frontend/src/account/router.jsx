import { useSyncExternalStore } from "react";
export function go(path, { replace = false } = {}) {
  history[replace ? "replaceState" : "pushState"](null, "", `#${path}`);
  window.dispatchEvent(new Event("app-route"));
}
function subscribe(fn) {
  window.addEventListener("popstate", fn);
  window.addEventListener("hashchange", fn);
  window.addEventListener("app-route", fn);
  return () => {
    window.removeEventListener("popstate", fn);
    window.removeEventListener("hashchange", fn);
    window.removeEventListener("app-route", fn);
  };
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

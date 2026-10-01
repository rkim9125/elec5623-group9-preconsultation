import React, { useEffect, useSyncExternalStore } from "react";
import { createRoot } from "react-dom/client";
import PatientPortal from "./account/Portal.jsx";
import Doctor from "./doctor/Doctor.jsx";
import { go, useRoute } from "./account/router.jsx";
import { accountService as api } from "./account/service.js";
import { safeReturn } from "./account/domain.js";
import { useI18n } from "./i18n/react.jsx";
import { tr } from "./i18n/core.js";
import "./styles.css";
function Redirect({ to }) {
  useEffect(() => go(to, { replace: true, bypass: true }), [to]);
  return <p role="status">{tr("loading.demo.information")}</p>;
}
function App() {
  useI18n();
  const route = useRoute();
  const auth = useSyncExternalStore(api.subscribe, api.getSnapshot);
  const [path, query = ""] = route.split("?");
  useEffect(() => {
    api.restore();
  }, []);
  useEffect(() => {
    if (auth.status !== "authenticated") return;
    const timer = setTimeout(
      () => api.expire(),
      Math.max(0, auth.expiresAt - Date.now()),
    );
    return () => clearTimeout(timer);
  }, [auth.status, auth.epoch, auth.expiresAt]);
  if (auth.status === "checking")
    return <p role="status">{tr("loading.demo.information")}</p>;
  if (path === "/doctor/login")
    return <Redirect to={`/login${query ? `?${query}` : ""}`} />;
  const doctor = path === "/doctor" || path.startsWith("/doctor/");
  const protectedRoute =
    path.startsWith("/") && !["/login", "/signup"].includes(path);
  if (protectedRoute) {
    if (auth.status !== "authenticated")
      return <Redirect to={`/login?returnTo=${encodeURIComponent(route)}`} />;
    if (doctor !== (auth.user.role === "doctor"))
      return <Redirect to={safeReturn(null, auth.user.role)} />;
  }
  return doctor ? (
    <Doctor key={auth.epoch} />
  ) : (
    <PatientPortal key={protectedRoute ? auth.epoch : "public"} />
  );
}
createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);

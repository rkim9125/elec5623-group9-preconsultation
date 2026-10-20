import React, { useEffect, useRef } from "react";
import Icon from "./Icons.jsx";
import { statusLabel } from "./api.js";
import { useLocale } from "./i18n.jsx";

export function Button({ children, icon, className = "", busy, ...props }) {
  return (
    <button
      className={`button ${className}`}
      {...props}
      disabled={props.disabled || busy}
    >
      {busy ? (
        <span className="spinner" />
      ) : icon ? (
        <Icon name={icon} size={17} />
      ) : null}
      {children}
    </button>
  );
}
export function ErrorNotice({ children }) {
  const { t } = useLocale();
  return children ? (
    <div className="notice error" role="alert">
      <Icon name="info" />
      <span>{typeof children === "string" ? t(children) : children}</span>
    </div>
  ) : null;
}
export function Loading({ label = "Loading your workspace…" }) {
  const { t } = useLocale();
  return (
    <div className="loading-state" role="status">
      <span className="spinner" />
      <p>{t(label)}</p>
    </div>
  );
}
export function Status({ status }) {
  const { t } = useLocale();
  return (
    <span className={`status status-${status}`}>
      <i />
      {t(statusLabel(status))}
    </span>
  );
}
export function Empty({ title, children, action, icon = "file" }) {
  const { t } = useLocale();
  return (
    <div className="empty-state">
      <span className="empty-icon">
        <Icon name={icon} size={29} />
      </span>
      <h3>{t(title)}</h3>
      <p>{typeof children === "string" ? t(children) : children}</p>
      {action}
    </div>
  );
}
export function Modal({ title, onClose, children, wide = false }) {
  const { t } = useLocale();
  const ref = useRef(null);
  useEffect(() => {
    const before = document.activeElement;
    const dialog = ref.current;
    dialog.showModal();
    return () => {
      dialog.close();
      before?.focus();
    };
  }, []);
  return (
    <dialog
      className={`modal ${wide ? "modal-wide" : ""}`}
      ref={ref}
      onCancel={(e) => {
        e.preventDefault();
        onClose();
      }}
      onClick={(e) => {
        if (e.target === ref.current) onClose();
      }}
      aria-labelledby="modal-title"
    >
      <div className="modal-heading">
        <h2 id="modal-title">{t(title)}</h2>
        <button
          className="icon-button"
          onClick={onClose}
          aria-label={t("Close dialog")}
        >
          <Icon name="close" />
        </button>
      </div>
      {children}
    </dialog>
  );
}

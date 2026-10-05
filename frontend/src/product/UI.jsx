import React, { useEffect, useRef } from "react";
import Icon from "./Icons.jsx";
import { statusLabel } from "./api.js";

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
  return children ? (
    <div className="notice error" role="alert">
      <Icon name="info" />
      <span>{children}</span>
    </div>
  ) : null;
}
export function Loading({ label = "Loading your workspace…" }) {
  return (
    <div className="loading-state" role="status">
      <span className="spinner" />
      <p>{label}</p>
    </div>
  );
}
export function Status({ status }) {
  return (
    <span className={`status status-${status}`}>
      <i />
      {statusLabel(status)}
    </span>
  );
}
export function Empty({ title, children, action, icon = "file" }) {
  return (
    <div className="empty-state">
      <span className="empty-icon">
        <Icon name={icon} size={29} />
      </span>
      <h3>{title}</h3>
      <p>{children}</p>
      {action}
    </div>
  );
}
export function Modal({ title, onClose, children, wide = false }) {
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
        <h2 id="modal-title">{title}</h2>
        <button
          className="icon-button"
          onClick={onClose}
          aria-label="Close dialog"
        >
          <Icon name="close" />
        </button>
      </div>
      {children}
    </dialog>
  );
}

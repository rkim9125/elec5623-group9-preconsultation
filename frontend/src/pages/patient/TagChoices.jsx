import { tr } from "../../i18n/core.js";

export default function TagChoices({
  id,
  title,
  help,
  note,
  options,
  selected,
  disabled,
  onChange,
}) {
  return (
    <fieldset aria-describedby={`${id}-help ${id}-examples`}>
      <legend>{tr(title)}</legend>
      <p id={`${id}-help`}>{tr(help)}</p>
      <p id={`${id}-examples`} className="footnote">
        {tr(note)}
      </p>
      <div className="history-tags">
        {options.map(({ id: value, labelKey }) => (
          <label
            key={value}
            className={`history-tag ${!disabled && selected.includes(value) ? "selected" : ""}`}
          >
            <input
              type="checkbox"
              checked={!disabled && selected.includes(value)}
              disabled={disabled}
              onChange={() =>
                onChange(
                  selected.includes(value)
                    ? selected.filter((tag) => tag !== value)
                    : [...selected, value],
                )
              }
            />
            <span className="history-check" aria-hidden="true">
              {!disabled && selected.includes(value) ? "✓" : "+"}
            </span>
            <span>{tr(labelKey)}</span>
          </label>
        ))}
      </div>
    </fieldset>
  );
}

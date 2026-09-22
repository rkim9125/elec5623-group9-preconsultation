import TagChoices from "./TagChoices.jsx";
import { tr } from "../../i18n/core.js";
import {
  historyOptions,
  historyTags,
  hasHistory,
  editHistory,
} from "../../history.js";

export default function HistoryInput({ answer, onChange, error }) {
  const inactive = ["none", "unknown", "declined"].includes(answer.status);
  const tags = historyTags(answer);
  return (
    <div className="history-input">
      <TagChoices
        id="history"
        title="medical.history"
        help="history.help"
        note="history.examples"
        options={historyOptions}
        selected={tags}
        disabled={inactive}
        onChange={(tags) => onChange(editHistory(answer, { tags }))}
      />
      <label className="input-label" htmlFor="free-answer">
        {tr("history.description")}
      </label>
      <textarea
        id="free-answer"
        rows={4}
        maxLength={3000}
        value={answer.value || ""}
        disabled={inactive}
        placeholder={tr("history.placeholder")}
        aria-invalid={!!error && !hasHistory(answer)}
        aria-describedby={
          error ? "form-error" : inactive ? "history-inactive" : undefined
        }
        onChange={(event) =>
          onChange(editHistory(answer, { value: event.target.value }))
        }
      />
      <fieldset className="history-response">
        <legend>{tr("history.alternatives")}</legend>
        <div className="alternatives">
          {[
            ["none", "none"],
            ["unknown", "not.sure"],
            ["declined", "prefer.not.to.answer"],
          ].map(([status, key]) => (
            <button
              type="button"
              key={status}
              aria-pressed={answer.status === status}
              onClick={() => onChange({ ...answer, status })}
            >
              {tr(key)}
            </button>
          ))}
        </div>
      </fieldset>
      {inactive && (
        <div className="info-note" id="history-inactive">
          <p>{tr("history.inactive")}</p>
          <button
            type="button"
            className="text-button"
            onClick={() => onChange(editHistory(answer, {}))}
          >
            {tr("history.resume")}
          </button>
        </div>
      )}
    </div>
  );
}

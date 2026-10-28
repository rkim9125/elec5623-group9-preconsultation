import React from "react";
import Icon from "./Icons.jsx";
import { useLocale } from "./i18n.jsx";
import { recordTitle, recordLabel, recordedValue } from "./recordLocale.js";
import {
  dimensionFor,
  symptomStatuses,
  symptomStories,
} from "./oldcartsModel.js";
import "./symptom-story.css";

export function SymptomContext({ field }) {
  const { t } = useLocale();
  const dimension = dimensionFor(field);
  if (!dimension) return null;
  return (
    <div className="symptom-step-context">
      <span>
        <Icon name={dimension.icon} size={16} />
        {t(dimension.label)}
      </span>
    </div>
  );
}

export default function SymptomOverview({
  session,
  onEdit,
  editableFields = [],
  disabled = false,
}) {
  const { t } = useLocale();
  const stories = symptomStories(session);
  if (!stories.length) return null;
  return (
    <details className="symptom-story" data-testid="symptom-story">
      <summary>
        <span className="symptom-story-symbol">
          <Icon name="message" size={21} />
        </span>
        <span className="symptom-story-summary">
          <strong>{t("Your symptom story")}</strong>
          <small>{t("Saved details, in your own words")}</small>
        </span>
        <Icon name="chevron" size={17} />
      </summary>
      <div className="symptom-story-body">
        <p className="symptom-story-note">
          {t(
            "A record of what you shared, not a health score. Unknown and skipped details stay clearly marked.",
          )}
        </p>
        {stories.map((story) => (
          <section
            key={story.concern_id}
            className="symptom-story-concern"
            aria-label={recordTitle(story.title, t)}
          >
            <h3>{recordTitle(story.title, t)}</h3>
            <dl className="symptom-story-list">
              {story.dimensions.map((dimension) => {
                const status = symptomStatuses[dimension.status];
                const editable = editableFields.find(
                  (field) =>
                    field.concern_id === story.concern_id &&
                    dimension.keys.includes(field.key),
                );
                return (
                  <div
                    key={dimension.id}
                    className={`symptom-story-row story-${dimension.status.toLowerCase()}`}
                  >
                    <dt>
                      <Icon name={dimension.icon} size={17} />
                      <span>{t(dimension.label)}</span>
                    </dt>
                    <dd>
                      <span className="symptom-story-status">
                        <Icon name={status.icon} size={13} />
                        {t(status.label)}
                      </span>
                      {dimension.values
                        .filter(
                          (entry) => entry.value != null && entry.value !== "",
                        )
                        .map((entry, index) => (
                          <p key={`${entry.key}-${index}`}>
                            {dimension.values.length > 1 && entry.label && (
                              <span className="symptom-value-state">
                                {recordLabel(entry.label, t)}:{" "}
                              </span>
                            )}
                            {entry.status !== "FILLED" && (
                              <span className="symptom-value-state">
                                {t(symptomStatuses[entry.status].label)}:{" "}
                              </span>
                            )}
                            {recordedValue(entry.value, t)}
                          </p>
                        ))}
                      {dimension.legacy.map((entry, index) => (
                        <p className="symptom-legacy" key={`legacy-${index}`}>
                          <span className="symptom-value-state">
                            {t("Earlier combined description")}:{" "}
                          </span>
                          {recordedValue(entry.value, t)}
                        </p>
                      ))}
                    </dd>
                    {onEdit && editable && (
                      <dd className="symptom-story-edit-cell">
                        <button
                          type="button"
                          className="symptom-story-edit"
                          disabled={disabled}
                          aria-label={t("Edit {detail} for {concern}", {
                            detail: t(dimension.label),
                            concern: recordTitle(story.title, t),
                          })}
                          onClick={() => onEdit(editable)}
                        >
                          <Icon name="edit" size={15} />
                          <span>{t("Edit")}</span>
                        </button>
                      </dd>
                    )}
                  </div>
                );
              })}
            </dl>
            {story.unrecorded > 0 && (
              <p className="symptom-story-gap">
                {t(
                  "{count} details not yet fully recorded. You can still continue.",
                  { count: story.unrecorded },
                )}
              </p>
            )}
          </section>
        ))}
      </div>
    </details>
  );
}

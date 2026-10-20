import React, { useEffect, useState } from "react";
import { request } from "./api.js";
import Icon from "./Icons.jsx";
import { Button, ErrorNotice, Loading, Modal } from "./UI.jsx";
import { useLocale } from "./i18n.jsx";
import {
  bloodGroupLabel,
  parseBloodGroup,
  updateBloodGroup,
} from "./bloodGroup.js";
import "./visual-inputs.css";

const profileSteps = [
  {
    key: "date_of_birth",
    label: "When were you born?",
    icon: "person",
    type: "date",
    hint: "Your age is calculated from your date of birth each time.",
  },
  {
    key: "sex_at_birth",
    label: "What was your sex recorded at birth?",
    icon: "heart",
    options: [
      ["female", "Female"],
      ["male", "Male"],
      ["intersex", "Intersex"],
      ["prefer_not_to_say", "Prefer not to say"],
    ],
  },
  {
    key: "blood_group",
    label: "Do you know your blood group?",
    icon: "heart",
    type: "blood",
    hint: "Choose A, B, AB or O if you know it. You can leave the + or − part unknown.",
  },
  {
    key: "medical_history",
    label: "Anything in your medical history to remember?",
    icon: "file",
    hint: "Past diagnoses and lasting conditions. Leave current symptoms for this consultation.",
  },
  {
    key: "surgical_history",
    label: "Have you had any operations?",
    icon: "shield",
    hint: "Include the procedure and approximate year, if known.",
  },
  {
    key: "family_history",
    label: "Any relevant family health history?",
    icon: "person",
  },
  {
    key: "accessibility_needs",
    label: "How can we make visits easier for you?",
    icon: "heart",
    hint: "Communication, mobility or accessibility needs you want remembered.",
  },
];
export function hasProfile(profile) {
  return profileSteps.some(({ key }) => !!profile?.[key]);
}
export default function ProfileWizard({ onClose, onSaved }) {
  const { t } = useLocale();
  const [profile, setProfile] = useState(null);
  const [step, setStep] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [review, setReview] = useState(false);
  useEffect(() => {
    let live = true;
    request("/auth/profile")
      .then((result) => {
        if (live) setProfile(result.profile);
      })
      .catch((err) => {
        if (live) setError(err.message);
      });
    return () => {
      live = false;
    };
  }, []);
  async function save() {
    setBusy(true);
    setError("");
    try {
      const result = await request("/auth/profile", {
        method: "PUT",
        body: Object.fromEntries(
          profileSteps.map(({ key }) => [key, profile[key] || ""]),
        ),
      });
      onSaved?.(result.profile);
      onClose();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }
  const field = profileSteps[step];
  const blood = parseBloodGroup(profile?.blood_group);
  return (
    <Modal
      title={t("Your remembered health profile")}
      onClose={busy ? () => {} : onClose}
      wide
    >
      <ErrorNotice>{error}</ErrorNotice>
      {!profile ? (
        !error && <Loading />
      ) : (
        <div className="profile-wizard">
          <p className="profile-promise">
            {t(
              "Saved to your account for future visits. You can change or clear any answer.",
            )}
          </p>
          <div className="wizard-progress">
            <span
              style={{
                width: `${(review ? 1 : (step + 1) / profileSteps.length) * 100}%`,
              }}
            />
          </div>
          {review ? (
            <>
              <h3>{t("Your profile, ready for next time.")}</h3>
              <dl className="profile-review">
                {profileSteps.map((item, index) => (
                  <div key={item.key}>
                    <dt>{t(item.label)}</dt>
                    <dd>
                      {(item.type === "blood"
                        ? bloodGroupLabel(profile[item.key], t)
                        : t(
                            item.options?.find(
                              ([value]) => value === profile[item.key],
                            )?.[1] || "",
                          )) ||
                        profile[item.key] ||
                        t("Not provided")}
                    </dd>
                    <button
                      type="button"
                      className="text-button"
                      disabled={busy}
                      onClick={() => {
                        setStep(index);
                        setReview(false);
                      }}
                    >
                      {t("Edit")}
                    </button>
                  </div>
                ))}
              </dl>
              <p className="field-hint">
                {t(
                  "Current medicines, allergies, measurements and symptoms are asked again each visit.",
                )}
              </p>
            </>
          ) : (
            <div key={field.key} className="profile-question wizard-enter">
              <div className="wizard-emblem">
                <Icon name={field.icon} size={34} />
              </div>
              <span className="overline">
                {t("ABOUT YOU")} · {step + 1} / {profileSteps.length}
              </span>
              <h3 id="profile-question">{t(field.label)}</h3>
              {field.hint && <p>{t(field.hint)}</p>}
              {field.type === "blood" ? (
                <div className="profile-blood-group">
                  <fieldset>
                    <legend>{t("Blood group (ABO)")}</legend>
                    <div className="profile-choices">
                      {["A", "B", "AB", "O", "unknown"].map((abo) => (
                        <button
                          key={abo}
                          type="button"
                          className={blood.abo === abo ? "selected" : ""}
                          aria-pressed={blood.abo === abo}
                          disabled={busy}
                          onClick={() =>
                            setProfile({
                              ...profile,
                              blood_group: updateBloodGroup(
                                profile.blood_group,
                                "abo",
                                blood.abo === abo ? "" : abo,
                              ),
                            })
                          }
                        >
                          {abo === "unknown" ? t("I don’t know") : abo}
                          {blood.abo === abo && <Icon name="check" size={15} />}
                        </button>
                      ))}
                    </div>
                  </fieldset>
                  {blood.abo && blood.abo !== "unknown" && (
                    <fieldset>
                      <legend>{t("Rh factor (optional)")}</legend>
                      <p>
                        {t("Only select + or − if you know your Rh factor.")}
                      </p>
                      <div className="profile-choices">
                        {[
                          ["+", "Positive (+)"],
                          ["-", "Negative (−)"],
                          ["", "I don’t know"],
                        ].map(([rh, label]) => (
                          <button
                            key={rh}
                            type="button"
                            className={blood.rh === rh ? "selected" : ""}
                            aria-pressed={blood.rh === rh}
                            disabled={busy}
                            onClick={() =>
                              setProfile({
                                ...profile,
                                blood_group: updateBloodGroup(
                                  profile.blood_group,
                                  "rh",
                                  rh,
                                ),
                              })
                            }
                          >
                            {t(label)}
                            {blood.rh === rh && <Icon name="check" size={15} />}
                          </button>
                        ))}
                      </div>
                    </fieldset>
                  )}
                </div>
              ) : field.options ? (
                <div className="profile-choices">
                  {field.options.map(([value, label]) => (
                    <button
                      type="button"
                      className={profile[field.key] === value ? "selected" : ""}
                      aria-pressed={profile[field.key] === value}
                      key={value}
                      onClick={() =>
                        setProfile({
                          ...profile,
                          [field.key]:
                            profile[field.key] === value ? "" : value,
                        })
                      }
                    >
                      {t(label)}
                      {profile[field.key] === value && (
                        <Icon name="check" size={15} />
                      )}
                    </button>
                  ))}
                </div>
              ) : field.type === "date" ? (
                <input
                  className="input"
                  type="date"
                  aria-labelledby="profile-question"
                  value={profile[field.key] || ""}
                  max={new Date().toISOString().slice(0, 10)}
                  onChange={(e) =>
                    setProfile({ ...profile, [field.key]: e.target.value })
                  }
                />
              ) : (
                <textarea
                  aria-labelledby="profile-question"
                  rows={4}
                  maxLength={4000}
                  value={profile[field.key] || ""}
                  placeholder={t("Share what you would like us to remember…")}
                  onChange={(e) =>
                    setProfile({ ...profile, [field.key]: e.target.value })
                  }
                />
              )}
              {profile[field.key] && (
                <button
                  className="text-button"
                  type="button"
                  onClick={() => setProfile({ ...profile, [field.key]: "" })}
                >
                  {t("Clear this answer")}
                </button>
              )}
            </div>
          )}
          <div className="wizard-actions">
            <Button
              className="secondary"
              disabled={busy || (!review && step === 0)}
              onClick={() => (review ? setReview(false) : setStep(step - 1))}
            >
              {t("Go back")}
            </Button>
            <Button
              className="primary"
              busy={busy}
              onClick={() =>
                review
                  ? save()
                  : step === profileSteps.length - 1
                    ? setReview(true)
                    : setStep(step + 1)
              }
            >
              {t(review ? "Save profile" : "Continue")}
              <Icon name="arrow" size={17} />
            </Button>
          </div>
        </div>
      )}
    </Modal>
  );
}

import React, { useEffect, useRef, useState } from "react";
import Icon from "./Icons.jsx";
import { attachmentUrl, dateLabel, reportPdf } from "./api.js";
import { Button, ErrorNotice, Modal } from "./UI.jsx";
import "./assessment-report.css";
import { useLocale } from "./i18n.jsx";
import { recordLabel, recordedValue, slotStatusLabel } from "./recordLocale.js";

const urgencyLabels = {
  emergency: "Emergency assessment advised",
  urgent: "Prompt clinical assessment advised",
  routine: "Plan a clinical consultation",
  uncertain: "Timing needs clinical clarification",
};


export default function AssessmentReport({
  session,
  busy,
  generating,
  error,
  onGenerate,
  configured = true,
}) {
  const { t } = useLocale();
  const [selectedSources, setSelectedSources] = useState(null);
  const outdated = session.ai_report?.status === "ready" &&
    (session.ai_report.localization_outdated || !session.ai_report.locale ||
      session.ai_report.locale !== (session.locale || "en"));
  const report =
    session.ai_report?.status === "ready" && (!outdated || session.status === "approved") ? session.ai_report : null;
  const sources = report?.sources || [];
  const canGenerate =
    ["review", "approved"].includes(session.status) &&
    !(outdated && session.status === "approved") &&
    !!session.summary &&
    !session.summary.needs_reconciliation &&
    !!session.consent;
  const attachments = session.attachments || [];
  const evidence = (ids = []) => {
    const available = sources.filter((source) => ids.includes(source.id));
    return available.length ? (
      <button
        type="button"
        className="source-link"
        onClick={() => setSelectedSources(available)}
        aria-label={t("View {count} supporting sources", {
          count: available.length,
        })}
      >
        <Icon name="file" size={12} />
        {t("{count} sources", { count: available.length })}
      </button>
    ) : null;
  };
  const items = (entries) => (
    <ul className="assessment-item-list">
      {(entries || []).map((item, index) => (
        <li key={index}>
          <span>{item.text}</span> {evidence(item.source_ids)}
        </li>
      ))}
    </ul>
  );

  return (
    <section className="assessment-report" aria-labelledby="assessment-title">
      <header className="assessment-heading">
        <span className="assessment-heading-icon">
          <Icon name="sparkle" size={25} />
        </span>
        <div>
          <span className="section-kicker">{t("YOUR AI HEALTH REPORT")}</span>
          <h2 id="assessment-title">
            {t("AI diagnosis & consultation guidance")}
          </h2>
          <p>
            {t(
              "Possible explanations, clinical questions and your next steps.",
            )}
          </p>
        </div>
      </header>
      <div className="assessment-boundary">
        <Icon name="shield" size={19} />
        <p>
          <strong>
            {t("Preliminary AI assessment · clinician confirmation required.")}
          </strong>{" "}
          {t(
            "These are possibilities, not a confirmed diagnosis. AI can make mistakes and cannot examine you. A clinician must verify the findings and decide on diagnosis and treatment.",
          )}
        </p>
      </div>

      <ErrorNotice>{error}</ErrorNotice>
      {outdated && (
        <div className="notice notice-info" role="status">
          {t(session.status === "approved"
            ? "This shared report keeps the language approved by the patient. Withdraw sharing before preparing a new version in another language."
            : "Prepare the assessment again to use your selected language. Your recorded answers remain saved.")}
        </div>
      )}
      {generating && (
        <div className="assessment-progress" role="status" aria-live="polite">
          <span className="spinner" />
          <div>
            <strong>
              {report
                ? t("Updating the AI assessment…")
                : t("Preparing your AI assessment…")}
            </strong>
            <p>
              {attachments.length
                ? t(
                    "Considering your recorded information and {count} uploaded attachments. This can take a few minutes. Your information is saved.",
                    { count: attachments.length },
                  )
                : t(
                    "Considering your recorded information. This can take a few minutes. Your information is saved.",
                  )}
            </p>
            {report && (
              <p>
                {t(
                  "The previous assessment remains below until the update is ready.",
                )}
              </p>
            )}
          </div>
        </div>
      )}

      {!report && !generating && (
        <div className="assessment-empty">
          <h3>{t("Your assessment is ready to prepare")}</h3>
          <p>
            {t(
              "Bring the health information, follow-up answers and uploaded files together into a preliminary assessment for you and your doctor. It will appear here separately from the factual summary below.",
            )}
          </p>
        </div>
      )}

      {report && (
        <div className="assessment-content">
          <div className="assessment-overview">
            <h3>{t("Assessment overview")}</h3>
            <p>
              {report.overview?.text} {evidence(report.overview?.source_ids)}
            </p>
          </div>

          {report.care_guidance && (
            <section
              className={`assessment-care assessment-care-${report.care_guidance.urgency}`}
            >
              <div className="assessment-care-title">
                <Icon name="clock" size={22} />
                <div>
                  <span className="section-kicker">
                    {t("WHEN TO SEEK CARE")}
                  </span>
                  <h3>
                    {t(
                      urgencyLabels[report.care_guidance.urgency] ||
                        "Consultation guidance",
                    )}
                  </h3>
                </div>
              </div>
              <p>
                <strong>{report.care_guidance.timeframe}</strong>
              </p>
              <p>
                {report.care_guidance.reason}{" "}
                {evidence(report.care_guidance.source_ids)}
              </p>
              <small>
                {t(
                  "AI advice is provisional. New or worsening symptoms can change the level of care needed.",
                )}
              </small>
            </section>
          )}

          <section className="assessment-section">
            <div className="assessment-section-heading">
              <Icon name="results" size={22} />
              <h3>{t("Possible diagnoses to discuss")}</h3>
            </div>
            <p className="assessment-section-intro">
              {t(
                "These possibilities need clinical evaluation. The list is not a diagnosis or a ranking of certainty.",
              )}
            </p>
            <div className="assessment-diagnoses">
              {(report.possible_diagnoses || []).map((diagnosis, index) => (
                <article key={index}>
                  <h4>{diagnosis.name}</h4>
                  <p>
                    {diagnosis.explanation} {evidence(diagnosis.source_ids)}
                  </p>
                  <div className="assessment-evidence-columns">
                    <div>
                      <h5>{t("What supports this possibility")}</h5>
                      <ul>
                        {(diagnosis.supporting_evidence || []).map(
                          (text, i) => (
                            <li key={i}>{text}</li>
                          ),
                        )}
                      </ul>
                    </div>
                    <div>
                      <h5>{t("Uncertainty & what needs checking")}</h5>
                      <ul>
                        {(diagnosis.uncertainties || []).map((text, i) => (
                          <li key={i}>{text}</li>
                        ))}
                      </ul>
                    </div>
                  </div>
                </article>
              ))}
            </div>
          </section>

          {!!report.next_steps?.length && (
            <section className="assessment-section">
              <div className="assessment-section-heading">
                <Icon name="check" size={21} />
                <h3>{t("Consultation plan & next steps")}</h3>
              </div>
              {items(report.next_steps)}
            </section>
          )}

          {!!report.red_flags?.length && (
            <section className="assessment-red-flags">
              <div className="assessment-section-heading">
                <Icon name="info" size={21} />
                <h3>{t("Symptoms that need urgent attention")}</h3>
              </div>
              <p>
                {t(
                  "These are warning signs to watch for, not a statement that you have them.",
                )}
              </p>
              {items(report.red_flags)}
              <p className="assessment-emergency">
                {t("For a medical emergency in Australia, call")}
                <strong>000</strong>.
              </p>
            </section>
          )}

          {!!report.missing_information?.length && (
            <section className="assessment-section">
              <div className="assessment-section-heading">
                <Icon name="file" size={21} />
                <h3>{t("Questions & information to clarify")}</h3>
              </div>
              {items(report.missing_information)}
            </section>
          )}

          {!!report.attachment_reviews?.length && (
            <section className="assessment-section">
              <div className="assessment-section-heading">
                <Icon name="upload" size={21} />
                <h3>{t("Uploaded documents & images")}</h3>
              </div>
              <p className="assessment-section-intro">
                {t(
                  "AI observations are unverified. Original images and every uploaded PDF page are included in the complete PDF for clinical review.",
                )}
              </p>
              <div className="assessment-files">
                {report.attachment_reviews.map((review) => {
                  const file = attachments.find(
                    (item) => item.id === review.attachment_id,
                  );
                  return (
                    <article key={review.attachment_id}>
                      {file && (
                        <a
                          href={attachmentUrl(session.id, file.id)}
                          target="_blank"
                          rel="noreferrer"
                          className="assessment-file-preview"
                          aria-label={`Open original ${file.filename}`}
                        >
                          {file.media_type?.startsWith("image/") ? (
                            <img
                              src={attachmentUrl(session.id, file.id)}
                              alt={`Uploaded attachment: ${file.filename}`}
                            />
                          ) : (
                            <Icon name="file" size={32} />
                          )}
                        </a>
                      )}
                      <div>
                        <h4>{review.filename}</h4>
                        <span
                          className={`assessment-file-status ${review.status === "limited" ? "limited" : ""}`}
                        >
                          {review.status === "limited"
                            ? t("Interpretation limited")
                            : t("AI processed · unverified")}
                        </span>
                        <p>
                          {review.findings} {evidence(review.source_ids)}
                        </p>
                        {review.limitations && (
                          <p className="assessment-file-limit">
                            <strong>{t("Limitations:")}</strong>{" "}
                            {review.limitations}
                          </p>
                        )}
                        {file && (
                          <a
                            className="assessment-original"
                            href={attachmentUrl(session.id, file.id)}
                            target="_blank"
                            rel="noreferrer"
                          >
                            {t("Open original file")}
                            <Icon name="arrow" size={13} />
                          </a>
                        )}
                      </div>
                    </article>
                  );
                })}
              </div>
            </section>
          )}

          {!!report.limitations?.length && (
            <section className="assessment-limitations">
              <h3>{t("Limits of this assessment")}</h3>
              <ul>
                {report.limitations.map((text, index) => (
                  <li key={index}>{text}</li>
                ))}
              </ul>
            </section>
          )}
          <p className="assessment-generated">
            {t("AI-generated")}
            {dateLabel(report.generated_at, true)}
            {t("· Summary version")}
            {report.summary_version} · {report.model}
          </p>
        </div>
      )}

      <div className="assessment-actions">
        {canGenerate && (
          <>
            <p>
              {t(
                "Generation uses your recorded information and all uploaded files. Both you and your authorised doctor can view this assessment after you approve sharing. Generating it does not mark it as clinician-approved.",
              )}
            </p>
            {!configured && (
              <p className="field-hint">
                {t(
                  "AI assessment is unavailable until the service administrator configures the AI connection.",
                )}
              </p>
            )}
            <Button
              className={report ? "secondary" : "primary"}
              icon="sparkle"
              busy={generating}
              disabled={busy || !configured}
              onClick={onGenerate}
            >
              {generating
                ? t("Preparing AI assessment…")
                : report
                  ? t("Regenerate AI assessment")
                  : error
                    ? t("Retry AI assessment")
                    : t("Generate AI assessment")}
            </Button>
          </>
        )}
        {!canGenerate && !report && (
          <p>
            {t(
              "Complete or revise the preparation summary before generating an assessment.",
            )}
          </p>
        )}
      </div>

      {selectedSources && (
        <Modal
          title={t("Supporting information")}
          onClose={() => setSelectedSources(null)}
        >
          <p className="modal-copy">
            {t(
              "These are the recorded details or attachment references cited by the AI. A citation does not confirm the proposed diagnosis.",
            )}
          </p>
          <dl className="source-modal-list">
            {selectedSources.map((source) => (
              <div key={source.id}>
                <dt>{recordLabel(source.label, t)}</dt>
                <dd>
                  {recordedValue(source.value, t)}
                  <small>
                    {slotStatusLabel(source.status, t)}
                  </small>
                </dd>
              </div>
            ))}
          </dl>
          <div className="modal-actions">
            <Button
              className="primary"
              onClick={() => setSelectedSources(null)}
            >
              {t("Done")}
            </Button>
          </div>
        </Modal>
      )}
    </section>
  );
}

export function ReportDownloadCard({ session, busy, onBusyChange }) {
  const { t } = useLocale();
  const patientLocale = session.locale || "en";
  const synthesis = session.summary?.synthesis;
  const outdated = patientLocale !== "en" && (
    (synthesis?.status === "live" && (!synthesis.locale || synthesis.locale !== patientLocale || synthesis.localization_outdated)) ||
    (session.ai_report?.status === "ready" && (!session.ai_report.locale || session.ai_report.locale !== patientLocale || session.ai_report.localization_outdated))
  );
  const [preparing, setPreparing] = useState(false);
  const [error, setError] = useState("");
  const mounted = useRef(true);
  const pending = useRef(false);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  async function download() {
    if (pending.current || busy || outdated) return;
    pending.current = true;
    setPreparing(true);
    setError("");
    onBusyChange(true);
    try {
      const blob = await reportPdf(session.id);
      if (!mounted.current) return;
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `PreConsult-report-${session.id.slice(0, 8)}.pdf`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 60000);
    } catch (err) {
      if (mounted.current) setError(err.message);
    } finally {
      pending.current = false;
      if (mounted.current) {
        setPreparing(false);
        onBusyChange(false);
      }
    }
  }
  return (
    <section
      className="complete-report-card"
      aria-labelledby="complete-report-title"
    >
      <span className="complete-report-icon">
        <Icon name="download" size={24} />
      </span>
      <h3 id="complete-report-title">{t("Your complete report")}</h3>
      <p>
        {t(
          session.ai_report?.status === "ready"
            ? "Save one PDF with your preparation summary, AI assessment and all uploaded images and PDF pages."
            : "Save one PDF with your preparation summary and all uploaded images and PDF pages.",
        )}
      </p>
      {!session.ai_report && (
        <p className="field-hint">
          {t(
            "Generate the AI assessment first to include diagnostic possibilities and consultation guidance. Otherwise, the PDF contains the factual summary and files only.",
          )}
        </p>
      )}
      <ErrorNotice>{error}</ErrorNotice>
      {outdated && <p className="field-hint">{t("Prepare your summary and assessment in this language before downloading the PDF.")}</p>}
      <Button
        className="primary full"
        icon="download"
        busy={preparing}
        disabled={busy || !session.summary || outdated}
        onClick={download}
      >
        {preparing ? t("Preparing complete PDF…") : t("Download complete PDF")}
      </Button>
      <p className="field-hint">
        {t(
          "{count} attached files · Images and original PDF pages are included.",
          { count: session.attachments?.length || 0 },
        )}
      </p>
    </section>
  );
}

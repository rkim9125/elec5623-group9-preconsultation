import React, { useEffect, useRef, useState } from "react";
import Icon from "./Icons.jsx";
import { attachmentUrl, dateLabel, reportPdf } from "./api.js";
import { Button, ErrorNotice, Modal } from "./UI.jsx";
import "./assessment-report.css";

const urgencyLabels = {
  emergency: "Emergency assessment advised",
  urgent: "Prompt clinical assessment advised",
  routine: "Plan a clinical consultation",
  uncertain: "Timing needs clinical clarification",
};

function sourceValue(source) {
  return source.value == null
    ? "Not provided"
    : typeof source.value === "string"
      ? source.value
      : JSON.stringify(source.value);
}

export default function AssessmentReport({
  session,
  busy,
  generating,
  error,
  onGenerate,
  configured = true,
}) {
  const [selectedSources, setSelectedSources] = useState(null);
  const report =
    session.ai_report?.status === "ready" ? session.ai_report : null;
  const sources = report?.sources || [];
  const canGenerate =
    ["review", "approved"].includes(session.status) &&
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
        aria-label={`View ${available.length} supporting sources`}
      >
        <Icon name="file" size={12} />
        {available.length} {available.length === 1 ? "source" : "sources"}
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
          <span className="section-kicker">YOUR AI HEALTH REPORT</span>
          <h2 id="assessment-title">
            AI diagnosis &amp; consultation guidance
          </h2>
          <p>Possible explanations, clinical questions and your next steps.</p>
        </div>
      </header>
      <div className="assessment-boundary">
        <Icon name="shield" size={19} />
        <p>
          <strong>
            Preliminary AI assessment · clinician confirmation required.
          </strong>{" "}
          These are possibilities, not a confirmed diagnosis. AI can make
          mistakes and cannot examine you. A clinician must verify the findings
          and decide on diagnosis and treatment.
        </p>
      </div>

      <ErrorNotice>{error}</ErrorNotice>
      {generating && (
        <div className="assessment-progress" role="status" aria-live="polite">
          <span className="spinner" />
          <div>
            <strong>
              {report
                ? "Updating the AI assessment…"
                : "Preparing your AI assessment…"}
            </strong>
            <p>
              Considering your recorded information
              {attachments.length > 0
                ? ` and all ${attachments.length} uploaded ${attachments.length === 1 ? "attachment" : "attachments"}`
                : ""}
              . This can take a few minutes. Your information is saved.
            </p>
            {report && (
              <p>
                The previous assessment remains below until the update is ready.
              </p>
            )}
          </div>
        </div>
      )}

      {!report && !generating && (
        <div className="assessment-empty">
          <h3>Your assessment is ready to prepare</h3>
          <p>
            Bring the health information, follow-up answers and uploaded files
            together into a preliminary assessment for you and your doctor. It
            will appear here separately from the factual summary below.
          </p>
        </div>
      )}

      {report && (
        <div className="assessment-content">
          <div className="assessment-overview">
            <h3>Assessment overview</h3>
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
                  <span className="section-kicker">WHEN TO SEEK CARE</span>
                  <h3>
                    {urgencyLabels[report.care_guidance.urgency] ||
                      "Consultation guidance"}
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
                AI advice is provisional. New or worsening symptoms can change
                the level of care needed.
              </small>
            </section>
          )}

          <section className="assessment-section">
            <div className="assessment-section-heading">
              <Icon name="results" size={22} />
              <h3>Possible diagnoses to discuss</h3>
            </div>
            <p className="assessment-section-intro">
              These possibilities need clinical evaluation. The list is not a
              diagnosis or a ranking of certainty.
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
                      <h5>What supports this possibility</h5>
                      <ul>
                        {(diagnosis.supporting_evidence || []).map(
                          (text, i) => (
                            <li key={i}>{text}</li>
                          ),
                        )}
                      </ul>
                    </div>
                    <div>
                      <h5>Uncertainty &amp; what needs checking</h5>
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
                <h3>Consultation plan &amp; next steps</h3>
              </div>
              {items(report.next_steps)}
            </section>
          )}

          {!!report.red_flags?.length && (
            <section className="assessment-red-flags">
              <div className="assessment-section-heading">
                <Icon name="info" size={21} />
                <h3>Symptoms that need urgent attention</h3>
              </div>
              <p>
                These are warning signs to watch for, not a statement that you
                have them.
              </p>
              {items(report.red_flags)}
              <p className="assessment-emergency">
                For a medical emergency in Australia, call <strong>000</strong>.
              </p>
            </section>
          )}

          {!!report.missing_information?.length && (
            <section className="assessment-section">
              <div className="assessment-section-heading">
                <Icon name="file" size={21} />
                <h3>Questions &amp; information to clarify</h3>
              </div>
              {items(report.missing_information)}
            </section>
          )}

          {!!report.attachment_reviews?.length && (
            <section className="assessment-section">
              <div className="assessment-section-heading">
                <Icon name="upload" size={21} />
                <h3>Uploaded documents &amp; images</h3>
              </div>
              <p className="assessment-section-intro">
                AI observations are unverified. Original images and every
                uploaded PDF page are included in the complete PDF for clinical
                review.
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
                            ? "Interpretation limited"
                            : "AI processed · unverified"}
                        </span>
                        <p>
                          {review.findings} {evidence(review.source_ids)}
                        </p>
                        {review.limitations && (
                          <p className="assessment-file-limit">
                            <strong>Limitations:</strong> {review.limitations}
                          </p>
                        )}
                        {file && (
                          <a
                            className="assessment-original"
                            href={attachmentUrl(session.id, file.id)}
                            target="_blank"
                            rel="noreferrer"
                          >
                            Open original file <Icon name="arrow" size={13} />
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
              <h3>Limits of this assessment</h3>
              <ul>
                {report.limitations.map((text, index) => (
                  <li key={index}>{text}</li>
                ))}
              </ul>
            </section>
          )}
          <p className="assessment-generated">
            AI-generated {dateLabel(report.generated_at, true)} · Summary
            version {report.summary_version} · {report.model}
          </p>
        </div>
      )}

      <div className="assessment-actions">
        {canGenerate && (
          <>
            <p>
              Generation uses your recorded information and all uploaded files.
              Both you and your authorised doctor can view this assessment after
              you approve sharing. Generating it does not mark it as
              clinician-approved.
            </p>
            {!configured && (
              <p className="field-hint">
                AI assessment is unavailable until the service administrator
                configures the AI connection.
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
                ? "Preparing AI assessment…"
                : report
                  ? "Regenerate AI assessment"
                  : error
                    ? "Retry AI assessment"
                    : "Generate AI assessment"}
            </Button>
          </>
        )}
        {!canGenerate && !report && (
          <p>
            Complete or revise the preparation summary before generating an
            assessment.
          </p>
        )}
      </div>

      {selectedSources && (
        <Modal
          title="Supporting information"
          onClose={() => setSelectedSources(null)}
        >
          <p className="modal-copy">
            These are the recorded details or attachment references cited by the
            AI. A citation does not confirm the proposed diagnosis.
          </p>
          <dl className="source-modal-list">
            {selectedSources.map((source) => (
              <div key={source.id}>
                <dt>{source.label}</dt>
                <dd>
                  {sourceValue(source)}
                  <small>{source.status?.toLowerCase().replace(/_/g, " ")}</small>
                </dd>
              </div>
            ))}
          </dl>
          <div className="modal-actions">
            <Button
              className="primary"
              onClick={() => setSelectedSources(null)}
            >
              Done
            </Button>
          </div>
        </Modal>
      )}
    </section>
  );
}

export function ReportDownloadCard({ session, busy, onBusyChange }) {
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
    if (pending.current || busy) return;
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
      <h3 id="complete-report-title">Your complete report</h3>
      <p>
        Save one PDF with the preparation summary
        {session.ai_report?.status === "ready" ? ", AI assessment" : ""} and all
        uploaded images and PDF pages.
      </p>
      {!session.ai_report && (
        <p className="field-hint">
          Generate the AI assessment first to include diagnostic possibilities
          and consultation guidance. Otherwise, the PDF contains the factual
          summary and files only.
        </p>
      )}
      <ErrorNotice>{error}</ErrorNotice>
      <Button
        className="primary full"
        icon="download"
        busy={preparing}
        disabled={busy || !session.summary}
        onClick={download}
      >
        {preparing ? "Preparing complete PDF…" : "Download complete PDF"}
      </Button>
      <p className="field-hint">
        {session.attachments?.length || 0} attached{" "}
        {session.attachments?.length === 1 ? "file" : "files"} · Images and
        original PDF pages are included.
      </p>
    </section>
  );
}

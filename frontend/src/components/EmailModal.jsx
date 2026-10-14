import { useState, useEffect, useRef, useMemo } from "react";
import { X, Reply, Send, User, Tag } from "lucide-react";
import { api } from "../api/client";
import { formatDate } from "../utils/date";

const STATUS_OPTIONS = [
  { value: "queued", label: "Queued" },
  { value: "read", label: "Read" },
  { value: "automated", label: "Automated" },
];

// Inbound HTML comes from external senders, not from us -- treat it as
// untrusted. This renders it inside a sandboxed iframe with scripts
// disabled, so nothing in the email can execute JS in our app's origin,
// while still letting layout/styling/tables/images render as intended.
function EmailHtmlFrame({ html }) {
  const iframeRef = useRef(null);
  const [height, setHeight] = useState(160);

  const srcDoc = useMemo(() => {
    // Strip <script> tags as defense in depth. The sandbox (no
    // allow-scripts) is what actually prevents execution; this just
    // keeps dead script tags out of the DOM entirely.
    const withoutScripts = (html || "").replace(
      /<script[\s\S]*?<\/script>/gi,
      ""
    );

    return `<!DOCTYPE html>
<html>
  <head>
    <meta charset="utf-8" />
    <base target="_blank" rel="noopener noreferrer" />
    <meta name="referrer" content="no-referrer" />
    <style>
      * { box-sizing: border-box; }
      html, body {
        margin: 0;
        padding: 0;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        font-size: 14px;
        line-height: 1.6;
        color: #1a1a1a;
        word-break: break-word;
        overflow-wrap: anywhere;
      }
      img { max-width: 100%; height: auto; }
      table { max-width: 100%; }
      a { color: #6c5ce7; }
      body { padding: 4px 2px; }
    </style>
  </head>
  <body>${withoutScripts}</body>
</html>`;
  }, [html]);

  function handleLoad() {
    try {
      const doc = iframeRef.current?.contentDocument;
      if (doc?.body) {
        // +16 for a little breathing room so scrollbars don't flicker in
        setHeight(doc.body.scrollHeight + 16);
      }
    } catch {
      // Cross-origin or otherwise inaccessible -- keep the fallback height.
    }
  }

  return (
    <iframe
      ref={iframeRef}
      title="Email content"
      srcDoc={srcDoc}
      onLoad={handleLoad}
      // No "allow-scripts" -- this is the actual security boundary.
      // allow-popups(-to-escape-sandbox) lets target="_blank" links open
      // a real new tab instead of being silently blocked.
      sandbox="allow-same-origin allow-popups allow-popups-to-escape-sandbox"
      style={{
        width: "100%",
        height,
        border: "none",
        display: "block",
      }}
    />
  );
}

// Until the backend stores body_html separately, HTML content sometimes
// arrives in snippet/body_text instead. Detect it by shape rather than
// trusting a specific field, so it still renders instead of showing raw
// markup as text.
function looksLikeHtml(value) {
  if (!value) return false;
  return /<\/?[a-z][\s\S]*>/i.test(value);
}

export default function EmailModal({ email, onClose, onReplied, onUpdated }) {
  const [replying, setReplying] = useState(false);
  const [replyText, setReplyText] = useState("");
  const [sending, setSending] = useState(false);
  const [sendError, setSendError] = useState(null);

  const [status, setStatus] = useState(email.status);
  const [statusSaving, setStatusSaving] = useState(false);
  const [statusError, setStatusError] = useState(null);

  const [classifications, setClassifications] = useState([]);
  const [classificationId, setClassificationId] = useState(
    email.classification_id || ""
  );
  const [classifySaving, setClassifySaving] = useState(false);
  const [classifyError, setClassifyError] = useState(null);

  const ccList = email.cc
    ? email.cc.split(",").map((s) => s.trim()).filter(Boolean)
    : [];

  useEffect(() => {
    api
      .listClassifications()
      .then(setClassifications)
      .catch(() => {
        // Non-critical -- the dropdown just stays empty if this fails.
      });
  }, []);

  async function handleStatusChange(e) {
    const newStatus = e.target.value;
    const previous = status;
    setStatus(newStatus); // optimistic
    setStatusSaving(true);
    setStatusError(null);
    try {
      await api.updateEmailStatus(email.id, newStatus);
      onUpdated?.(email.id, { status: newStatus });
    } catch (err) {
      setStatus(previous); // revert on failure
      setStatusError(err.message || "Failed to update status");
    } finally {
      setStatusSaving(false);
    }
  }

  async function handleClassifyChange(e) {
    const newId = e.target.value;
    const previous = classificationId;
    setClassificationId(newId); // optimistic
    setClassifySaving(true);
    setClassifyError(null);
    try {
      await api.classifyEmail(email.id, newId || null);
      onUpdated?.(email.id, { classification_id: newId || null });
    } catch (err) {
      setClassificationId(previous); // revert on failure
      setClassifyError(err.message || "Failed to classify email");
    } finally {
      setClassifySaving(false);
    }
  }

  async function handleSend() {
    if (!replyText.trim()) return;
    setSending(true);
    setSendError(null);
    try {
      await api.replyEmail(email.id, replyText.trim());
      onReplied(email.id, replyText.trim());
      setReplying(false);
      setReplyText("");
    } catch (err) {
      setSendError(err.message || "Failed to send reply");
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div
        className="modal-panel email-modal"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-header">
          <h2>{email.subject || "(no subject)"}</h2>
          <button className="icon-btn" onClick={onClose} title="Close">
            <X size={16} />
          </button>
        </div>

        <div className="email-meta">
          <div className="email-meta-row">
            <User size={14} />
            <span className="email-meta-label">From</span>
            <span className="email-meta-value">{email.sender}</span>
          </div>

          {email.recipient && (
            <div className="email-meta-row">
              <span className="email-meta-label">To</span>
              <span className="email-meta-value">{email.recipient}</span>
            </div>
          )}

          {ccList.length > 0 && (
            <div className="email-meta-row">
              <span className="email-meta-label">Cc</span>
              <span className="email-meta-value">{ccList.join(", ")}</span>
            </div>
          )}

          <div className="email-meta-row">
            <span className="email-meta-label">Received</span>
            <span className="email-meta-value">
              {formatDate(email.received_at)}
            </span>
          </div>
        </div>

        <div className="email-controls">
          <div className="email-control">
            <label htmlFor="email-status-select">Status</label>
            <select
              id="email-status-select"
              className="select-input"
              value={status}
              onChange={handleStatusChange}
              disabled={statusSaving}
            >
              {STATUS_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

          <div className="email-control">
            <label htmlFor="email-classify-select">
              <Tag size={12} /> Classify as
            </label>
            <select
              id="email-classify-select"
              className="select-input"
              value={classificationId}
              onChange={handleClassifyChange}
              disabled={classifySaving}
            >
              <option value="">Unclassified</option>
              {classifications.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </div>
        </div>

        {(statusError || classifyError) && (
          <div className="alert error visible" style={{ margin: "0 22px 12px" }}>
            {statusError || classifyError}
          </div>
        )}

        <div className="email-body">
          {(() => {
            const rawBody = email.body_html || email.body_text || email.snippet || "";
            const isHtml = Boolean(email.body_html) || looksLikeHtml(rawBody);
            return isHtml ? (
              <EmailHtmlFrame html={rawBody} />
            ) : (
              <pre className="email-body-text">{rawBody || "(no content)"}</pre>
            );
          })()}
        </div>

        {email.replied && email.reply_body && !replying && (
          <div className="email-prior-reply">
            <div className="field-label">Your reply</div>
            <div className="prompt-box">{email.reply_body}</div>
          </div>
        )}

        <div className="email-modal-footer">
          {!replying ? (
            <button className="secondary-btn" onClick={() => setReplying(true)}>
              <Reply size={14} />
              {email.replied ? "Reply again" : "Reply"}
            </button>
          ) : (
            <div className="reply-box">
              <textarea
                className="textarea"
                rows={5}
                autoFocus
                placeholder="Write your reply…"
                value={replyText}
                onChange={(e) => setReplyText(e.target.value)}
              />
              {sendError && (
                <div className="alert error visible">{sendError}</div>
              )}
              <div className="reply-box-actions">
                <button
                  className="secondary-btn"
                  onClick={() => {
                    setReplying(false);
                    setReplyText("");
                    setSendError(null);
                  }}
                  disabled={sending}
                >
                  Cancel
                </button>
                <button
                  className="primary-btn"
                  onClick={handleSend}
                  disabled={sending || !replyText.trim()}
                >
                  <Send size={14} />
                  {sending ? "Sending…" : "Send reply"}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
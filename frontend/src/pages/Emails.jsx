import { useState, useEffect, useCallback, useMemo } from "react";
import { api } from "../api/client";
import { formatDate } from "../utils/date";
import TopBar from "../components/TopBar";
import EmailModal from "../components/EmailModal";
import { Search, Inbox, Reply, Eye } from "lucide-react";

const STATUS_FILTERS = [
  { key: "all", label: "All" },
  { key: "queued", label: "Queued" },
  { key: "read", label: "Read" },
  { key: "automated", label: "Automated" },
];
import "../styles/emails.css";

// The snippet column sometimes holds raw HTML (until the backend splits
// out a dedicated body_html field). Strip tags for the table preview so
// rows show clean text instead of markup.
function previewText(value, maxLength = 140) {
  if (!value) return "";
  const stripped = value.replace(/<[^>]*>/g, " ").replace(/\s+/g, " ").trim();
  return stripped.length > maxLength
    ? `${stripped.slice(0, maxLength)}…`
    : stripped;
}

export default function Emails() {
  const [emails, setEmails] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);

  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [repliedOnly, setRepliedOnly] = useState(false);

  const [selectedEmail, setSelectedEmail] = useState(null);

  const loadEmails = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const list = await api.listEmails({
        search: search || undefined,
        status: statusFilter !== "all" ? statusFilter : undefined,
      });
      setEmails(list);
    } catch (err) {
      setLoadError(err.message || "Failed to load emails");
    } finally {
      setLoading(false);
    }
  }, [search, statusFilter]);

  useEffect(() => {
    const timeout = setTimeout(loadEmails, 300); // debounce search
    return () => clearTimeout(timeout);
  }, [loadEmails]);

  const visibleEmails = useMemo(() => {
    if (!repliedOnly) return emails;
    return emails.filter((e) => e.replied);
  }, [emails, repliedOnly]);

  async function handleOpenEmail(email) {
    try {
      const full = await api.getEmail(email.id);
      setSelectedEmail(full);
      if (email.status === "queued") {
        api.markEmailRead(email.id).catch(() => {});
        setEmails((prev) =>
          prev.map((e) => (e.id === email.id ? { ...e, status: "read" } : e))
        );
      }
    } catch (err) {
      console.error("Failed to open email", err);
    }
  }

  function handleReplied(id, replyBody) {
    setEmails((prev) =>
      prev.map((e) =>
        e.id === id
          ? { ...e, replied: true, reply_body: replyBody, status: "read" }
          : e
      )
    );
    setSelectedEmail((prev) =>
      prev && prev.id === id
        ? { ...prev, replied: true, reply_body: replyBody }
        : prev
    );
  }

  function handleUpdated(id, patch) {
    setEmails((prev) =>
      prev.map((e) => (e.id === id ? { ...e, ...patch } : e))
    );
    setSelectedEmail((prev) =>
      prev && prev.id === id ? { ...prev, ...patch } : prev
    );
  }

  return (
    <>
      <TopBar />
      <div className="dash-wrap">
        <div className="dash-hello">
          <div className="eyebrow">Mailbox</div>
          <h1>Emails</h1>
        </div>

        <div className="email-toolbar">
          <div className="search-box">
            <Search size={15} />
            <input
              type="text"
              placeholder="Search by sender or subject…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>

          <div className="tab-row" style={{ marginBottom: 0 }}>
            {STATUS_FILTERS.map(({ key, label }) => (
              <button
                key={key}
                className={`tab-btn${statusFilter === key ? " active" : ""}`}
                onClick={() => setStatusFilter(key)}
              >
                {label}
              </button>
            ))}
          </div>

          <label className="replied-toggle">
            <input
              type="checkbox"
              checked={repliedOnly}
              onChange={(e) => setRepliedOnly(e.target.checked)}
            />
            Replied only
          </label>
        </div>

        {loading && <div className="loading-state">Loading emails…</div>}

        {loadError && !loading && (
          <div className="alert error visible" style={{ marginBottom: 24 }}>
            {loadError}
          </div>
        )}

        {!loading && !loadError && (
          <>
            {visibleEmails.length === 0 ? (
              <div className="empty-state">
                <Inbox size={22} style={{ marginBottom: 8, opacity: 0.5 }} />
                <div>No emails match your search or filters.</div>
              </div>
            ) : (
              <div className="email-table-wrap">
                <table className="email-table">
                  <colgroup>
                    <col style={{ width: "18%" }} />
                    <col style={{ width: "42%" }} />
                    <col style={{ width: "16%" }} />
                    <col style={{ width: "16%" }} />
                    <col style={{ width: "8%" }} />
                  </colgroup>
                  <thead>
                    <tr>
                      <th>From</th>
                      <th>Subject</th>
                      <th>Status</th>
                      <th>Received</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {visibleEmails.map((email) => (
                      <tr
                        key={email.id}
                        className={`email-row${
                          email.status === "queued" ? " unread" : ""
                        }`}
                        onClick={() => handleOpenEmail(email)}
                      >
                        <td className="cell-sender">{email.sender}</td>
                        <td className="cell-subject">
                          <span className="cell-subject-text">
                            {email.subject || "(no subject)"}
                          </span>
                          {email.snippet && (
                            <span className="cell-snippet">
                              {" — "}
                              {previewText(email.snippet)}
                            </span>
                          )}
                        </td>
                        <td className="cell-status">
                          <span
                            className={`badge ${
                              email.status === "queued"
                                ? "warn"
                                : email.status === "automated"
                                ? "info"
                                : "ok"
                            }`}
                          >
                            {email.status}
                          </span>
                          {email.replied && (
                            <span className="badge ok reply-badge">
                              <Reply size={11} /> replied
                            </span>
                          )}
                        </td>
                        
                        <td className="cell-date">
                          {formatDate(email.received_at)}
                        </td>
                        <td className="cell-actions">
                          <button
                            className="icon-btn"
                            title="View email"
                            onClick={(e) => {
                              e.stopPropagation();
                              handleOpenEmail(email);
                            }}
                          >
                            <Eye size={14} />
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}
      </div>

      {selectedEmail && (
        <EmailModal
          email={selectedEmail}
          onClose={() => setSelectedEmail(null)}
          onReplied={handleReplied}
          onUpdated={handleUpdated}
        />
      )}
    </>
  );
}
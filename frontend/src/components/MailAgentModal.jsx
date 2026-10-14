import { useState } from "react";
import { X, Trash2 } from "lucide-react";
import { api } from "../api/client";

export default function MailAgentModal({
  mode, // "create" | "edit"
  agent, // present in edit mode
  availableInboxCredentials, // email credentials not already claimed by another agent
  allEmailCredentials, // every email credential, for picking a separate sender
  onClose,
  onSaved,
  onDeleted,
}) {
  const isEdit = mode === "edit";

  const [name, setName] = useState(isEdit ? agent.name : "");
  const [inboxCredentialId, setInboxCredentialId] = useState(
    isEdit ? agent.inbox_credential_id : availableInboxCredentials[0]?.id || ""
  );
  const [useSeparateSender, setUseSeparateSender] = useState(
    isEdit ? Boolean(agent.sender_credential_id) : false
  );
  const [senderCredentialId, setSenderCredentialId] = useState(
    isEdit ? agent.sender_credential_id || "" : ""
  );
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [confirmingDelete, setConfirmingDelete] = useState(false);

  const senderChoices = allEmailCredentials.filter((c) => c.id !== inboxCredentialId);

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);

    if (!name.trim()) {
      setError("Give this agent a name so you can recognize it later.");
      return;
    }
    const senderId = useSeparateSender ? senderCredentialId : null;
    if (useSeparateSender && !senderId) {
      setError("Pick a mailbox to send from, or turn off the separate-sender option.");
      return;
    }

    setSubmitting(true);
    try {
      let saved;
      if (isEdit) {
        saved = await api.updateMailAgent(agent.id, {
          name: name.trim(),
          sender_credential_id: senderId,
          clear_sender_credential: !useSeparateSender,
        });
      } else {
        if (!inboxCredentialId) {
          setError("Pick a mailbox to monitor.");
          setSubmitting(false);
          return;
        }
        saved = await api.createMailAgent(name.trim(), inboxCredentialId, senderId);
      }
      onSaved(saved);
      onClose();
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDelete() {
    setSubmitting(true);
    try {
      await api.deleteMailAgent(agent.id);
      onDeleted(agent.id);
      onClose();
    } catch (err) {
      setError(err.message);
      setSubmitting(false);
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div>
            <h2>{isEdit ? "Edit mail agent" : "New mail agent"}</h2>
            <p>
              {isEdit
                ? "Rename, change the sending mailbox, or remove this agent."
                : "Pick a mailbox to monitor -- it gets its own dedicated agent."}
            </p>
          </div>
          <button type="button" className="modal-close" onClick={onClose} aria-label="Close">
            <X size={16} />
          </button>
        </div>

        {error && <div className="alert error visible">{error}</div>}

        <form onSubmit={handleSubmit}>
          <div className="field">
            <label htmlFor="agent-name">Agent name</label>
            <input
              id="agent-name"
              type="text"
              placeholder="e.g. Support Inbox Agent"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
            />
          </div>

          {!isEdit && (
            <div className="field">
              <label htmlFor="agent-inbox">Mailbox to monitor</label>
              <select
                id="agent-inbox"
                value={inboxCredentialId}
                onChange={(e) => setInboxCredentialId(e.target.value)}
                required
              >
                {availableInboxCredentials.length === 0 && <option value="">No mailboxes available</option>}
                {availableInboxCredentials.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.label}
                  </option>
                ))}
              </select>
              <div className="field-hint">
                Only mailboxes without an agent yet are listed. Add one in Settings first if you
                don't see it here.
              </div>
            </div>
          )}

          <div className="checkbox-field">
            <input
              id="agent-separate-sender"
              type="checkbox"
              checked={useSeparateSender}
              onChange={(e) => setUseSeparateSender(e.target.checked)}
            />
            <label htmlFor="agent-separate-sender">Send from a different mailbox</label>
          </div>

          {useSeparateSender && (
            <div className="field">
              <label htmlFor="agent-sender">Sending mailbox</label>
              <select
                id="agent-sender"
                value={senderCredentialId}
                onChange={(e) => setSenderCredentialId(e.target.value)}
              >
                <option value="">Select a mailbox…</option>
                {senderChoices.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.label}
                  </option>
                ))}
              </select>
              <div className="field-hint">
                The agent will reply and send from this mailbox instead of the monitored one.
              </div>
            </div>
          )}

          <div className="modal-footer">
            {isEdit && (
              <button
                type="button"
                className="icon-btn danger"
                onClick={() => setConfirmingDelete(true)}
                title="Delete agent"
              >
                <Trash2 size={15} />
              </button>
            )}
            <button type="submit" className="btn-primary" disabled={submitting}>
              {submitting ? "Saving…" : isEdit ? "Save changes" : "Create agent"}
            </button>
          </div>
        </form>

        {confirmingDelete && (
          <div className="alert error visible" style={{ marginTop: 16 }}>
            Delete "{agent.name}"? This can't be undone.
            <div style={{ display: "flex", gap: 8, marginTop: 10 }}>
              <button type="button" className="btn-ghost" onClick={() => setConfirmingDelete(false)}>
                Cancel
              </button>
              <button
                type="button"
                className="btn-primary"
                style={{ background: "var(--danger)" }}
                onClick={handleDelete}
                disabled={submitting}
              >
                {submitting ? "Deleting…" : "Delete"}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

import { useState } from "react";
import { X, Trash2 } from "lucide-react";
import { api } from "../api/client";

export default function ClassificationModal({
  mode = "create",      // "create" | "edit"
  classification,        // present in edit mode
  onClose,
  onSaved,
  onDeleted,
}) {
  const isEdit = mode === "edit";

  const [name, setName] = useState(isEdit ? classification?.name || "" : "");
  const [prompt, setPrompt] = useState(
    isEdit ? classification?.prompt || "" : ""
  );
  const [keywords, setKeywords] = useState(
    isEdit && classification?.keywords
      ? classification.keywords.join(", ")
      : ""
  );

  const [enabled, setEnabled] = useState(
    isEdit ? classification?.enabled ?? true : true
  );

  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [confirmingDelete, setConfirmingDelete] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);

    if (!name.trim()) {
      setError("Name is required.");
      return;
    }
    if (!prompt.trim()) {
      setError("Prompt is required.");
      return;
    }

    const payload = {
      name: name.trim(),
      prompt: prompt.trim(),
      keywords: keywords
        .split(",")
        .map((k) => k.trim())
        .filter(Boolean),
      enabled,
    };

    setSubmitting(true);
    try {
      let saved;
      if (isEdit) {
        saved = await api.updateClassification(classification.id, payload);
      } else {
        saved = await api.createClassification(payload);
      }
      if (onSaved) onSaved(saved);
      if (onClose) onClose();
    } catch (err) {
      setError(err.message || "Failed to save classification");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDelete() {
    if (!classification || !onDeleted) return;
    setSubmitting(true);
    setError(null);
    try {
      await api.deleteClassification(classification.id);
      onDeleted(classification.id);
      if (onClose) onClose();
    } catch (err) {
      setError(err.message || "Failed to delete classification");
      setSubmitting(false);
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div>
            <h2>
              {isEdit ? "Edit email classification" : "New email classification"}
            </h2>
            <p>
              {isEdit
                ? "Update the rule used to classify incoming emails."
                : "Define how emails should be classified using keywords and a prompt."}
            </p>
          </div>
          <button
            type="button"
            className="modal-close"
            onClick={onClose}
            aria-label="Close"
          >
            <X size={16} />
          </button>
        </div>

        {error && <div className="alert error visible">{error}</div>}

        <form onSubmit={handleSubmit}>
          <div className="field">
            <label htmlFor="classification-name">Name</label>
            <input
              id="classification-name"
              type="text"
              placeholder="e.g. Support tickets, Billing, Sales leads"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
            />
          </div>

<div className="field">
  <label htmlFor="classification-prompt">Prompt</label>
  <textarea
    id="classification-prompt"
    className="textarea"
    rows={5}
    value={prompt}
    onChange={(e) => setPrompt(e.target.value)}
    placeholder="Instruction for the LLM on how to classify emails."
    required
  />
</div>

          <div className="field">
            <label htmlFor="classification-keywords">Keywords (comma-separated)</label>
            <input
              id="classification-keywords"
              type="text"
              value={keywords}
              onChange={(e) => setKeywords(e.target.value)}
              placeholder="e.g. support, bug, issue, error"
            />
            <div className="field-hint">
              These keywords help pre-filter emails before applying the prompt.
            </div>
          </div>


          <div className="checkbox-field">
            <input
              id="classification-enabled"
              type="checkbox"
              checked={enabled}
              onChange={(e) => setEnabled(e.target.checked)}
            />
            <label htmlFor="classification-enabled">Enabled</label>
          </div>

          <div className="modal-footer">
            {isEdit && (
              <button
                type="button"
                className="icon-btn danger"
                onClick={() => setConfirmingDelete(true)}
                title="Delete classification"
              >
                <Trash2 size={15} />
              </button>
            )}
            <button type="submit" className="btn-primary" disabled={submitting}>
              {submitting
                ? "Saving…"
                : isEdit
                ? "Save changes"
                : "Create classification"}
            </button>
          </div>
        </form>

        {confirmingDelete && (
          <div className="alert error visible" style={{ marginTop: 16 }}>
            Delete "{classification.name}"? This can't be undone.
            <div style={{ display: "flex", gap: 8, marginTop: 10 }}>
              <button
                type="button"
                className="btn-ghost"
                onClick={() => setConfirmingDelete(false)}
              >
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
import { useEffect, useMemo, useState } from "react";
import { X, Trash2 } from "lucide-react";
import { api } from "../api/client";
import { providerIcon } from "../utils/providerIcons";

const CHECKBOX_FIELDS = new Set(["use_tls", "use_ssl"]);

const PROVIDER_OPTIONS = [
  { value: "openai", label: "OpenAI" },
  { value: "anthropic", label: "Anthropic" },
  { value: "gemini", label: "Gemini" },
  { value: "ollama", label: "Ollama" },
];

const OPENAI_MODELS = [
  { value: "gpt-4.1", label: "gpt-4.1" },
  { value: "gpt-4.1-mini", label: "gpt-4.1-mini" },
  { value: "gpt-4o", label: "gpt-4o" },
  { value: "gpt-4o-mini", label: "gpt-4o-mini" },
];

const OLLAMA_MODELS = [
  { value: "llama3.1:8b", label: "llama3.1:8b" },
  { value: "llama3.2:3b", label: "llama3.2:3b" },
  { value: "mistral:7b", label: "mistral:7b" },
  { value: "phi3:mini", label: "phi3:mini" },
  { value: "gemma3:4b", label: "gemma3:4b" },
];

function inputTypeFor(field) {
  if (CHECKBOX_FIELDS.has(field.name)) return "checkbox";
  if (field.name === "port") return "number";
  return field.kind === "secret" ? "password" : "text";
}

function fieldLabel(name) {
  return name
    .split("_")
    .map((w) => w[0].toUpperCase() + w.slice(1))
    .join(" ");
}

function getDefaultModel(provider) {
  if (provider === "openai") return OPENAI_MODELS[0]?.value || "";
  if (provider === "ollama") return OLLAMA_MODELS[0]?.value || "";
  return "";
}

export default function CredentialModal({
  mode,
  category,
  providerSpec,
  credential,
  onClose,
  onSaved,
  onDeleted,
}) {
  const isEdit = mode === "edit";
  const initialProvider = isEdit ? credential.provider : providerSpec.provider || "openai";

  const [provider, setProvider] = useState(initialProvider);
  const [model_name, setModelName] = useState(
    credential?.model_name || getDefaultModel(initialProvider)
  );
  const Icon = providerIcon(provider);

  const [label, setLabel] = useState(isEdit ? credential.label : "");
  const [values, setValues] = useState({});
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [confirmingDelete, setConfirmingDelete] = useState(false);

  const providerFields = useMemo(() => {
    if (provider === "ollama") return [];
    return providerSpec.fields || [];
  }, [provider, providerSpec]);

  const modelOptions =
    provider === "ollama"
      ? OLLAMA_MODELS
      : provider === "openai"
        ? OPENAI_MODELS
        : [];

  useEffect(() => {
    const nextProvider = isEdit ? credential.provider : providerSpec.provider || "openai";
    setProvider(nextProvider);
    setModelName(isEdit ? (credential.model_name || getDefaultModel(nextProvider)) : getDefaultModel(nextProvider));

    if (!credential) {
      setLabel("");
      const initial = {};
      for (const field of providerFields) {
        initial[field.name] = CHECKBOX_FIELDS.has(field.name) ? "false" : "";
      }
      setValues(initial);
      setError(null);
      setConfirmingDelete(false);
      return;
    }

    setLabel(credential.label || "");
    const initial = {};
    for (const field of providerFields) {
      if (field.kind === "text" && credential.masked_preview?.[field.name] !== undefined) {
        initial[field.name] = String(credential.masked_preview[field.name]);
      } else {
        initial[field.name] = CHECKBOX_FIELDS.has(field.name) ? "false" : "";
      }
    }
    setValues(initial);
    setError(null);
    setConfirmingDelete(false);
  }, [credential, providerSpec, providerFields, isEdit]);

  function setValue(name, value) {
    setValues((v) => ({ ...v, [name]: value }));
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);

    if (!label.trim()) {
      setError("Give this credential a name so you can recognize it later.");
      return;
    }

    if ((provider === "openai" || provider === "ollama") && !model_name) {
      setError("Please select a model.");
      return;
    }

    const secret = {};
    for (const field of providerFields) {
      const raw = values[field.name];
      if (raw !== "" && raw !== undefined) secret[field.name] = raw;
    }

    if (!isEdit) {
      const missing = providerFields.filter((f) => f.required && !secret[f.name]);
      if (missing.length > 0) {
        setError(
          `Missing required field(s): ${missing.map((f) => fieldLabel(f.name)).join(", ")}`
        );
        return;
      }
    }

    setSubmitting(true);
    try {
      let saved;

      const payloadExtra = {
        provider,
        model_name: provider === "openai" || provider === "ollama" ? model_name : null,
      };

      if (isEdit) {
        const payload = { label: label.trim(), ...payloadExtra };
        if (Object.keys(secret).length > 0) payload.secret = secret;
        saved = await api.updateCredential(credential.id, payload);
      } else {
        saved = await api.createCredential(
          category,
          provider,
          label.trim(),
          secret,
          model_name
        );
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
      await api.deleteCredential(credential.id);
      onDeleted(credential.id);
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
          <div className="modal-header-icon">
            <Icon size={18} />
          </div>
          <div>
            <h2>{isEdit ? "Edit Credential" : "Add Credential"}</h2>
            <p>
              {isEdit
                ? "Rename or update this credential."
                : "Stored encrypted, never shown in plain text again."}
            </p>
          </div>
          <button type="button" className="modal-close" onClick={onClose} aria-label="Close">
            <X size={16} />
          </button>
        </div>

        {error && <div className="alert error visible">{error}</div>}

        <form onSubmit={handleSubmit}>
          <div className="field">
            <label htmlFor="cred-label">Name</label>
            <input
              id="cred-label"
              type="text"
              placeholder="e.g. Prod OpenAI key"
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              required
            />
          </div>
          
          {category !== "email" && (
            <div className="field">
              <label htmlFor="provider">Provider</label>
              <select
                id="provider"
                value={provider}
                onChange={(e) => {
                  const nextProvider = e.target.value;
                  setProvider(nextProvider);
                  setModelName(getDefaultModel(nextProvider));
                  setValues({});
                }}
                disabled={isEdit}
              >
                {PROVIDER_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>
          )}


          {(provider === "openai" || provider === "ollama") && (
            <div className="field">
              <label htmlFor="model-name">Model name</label>
              <select
                id="model-name"
                value={model_name}
                onChange={(e) => setModelName(e.target.value)}
              >
                <option value="">Choose a model...</option>
                {modelOptions.map((model) => (
                  <option key={model.value} value={model.value}>
                    {model.label}
                  </option>
                ))}
              </select>
            </div>
          )}

          {providerFields.map((field) => {
            const type = inputTypeFor(field);
            const existingMasked =
              isEdit && field.kind === "secret"
                ? credential.masked_preview?.[field.name]
                : null;

            if (type === "checkbox") {
              return (
                <div className="checkbox-field" key={field.name}>
                  <input
                    id={`cred-${field.name}`}
                    type="checkbox"
                    checked={values[field.name] === "true"}
                    onChange={(e) =>
                      setValue(field.name, e.target.checked ? "true" : "false")
                    }
                  />
                  <label htmlFor={`cred-${field.name}`}>{fieldLabel(field.name)}</label>
                </div>
              );
            }

            return (
              <div className="field" key={field.name}>
                <label htmlFor={`cred-${field.name}`}>
                  {fieldLabel(field.name)}
                  {field.required && !isEdit ? " *" : ""}
                </label>
                <input
                  id={`cred-${field.name}`}
                  type={type}
                  value={values[field.name] || ""}
                  onChange={(e) => setValue(field.name, e.target.value)}
                  placeholder={
                    existingMasked
                      ? `Current: ${existingMasked} — leave blank to keep`
                      : ""
                  }
                  autoComplete={type === "password" ? "new-password" : "off"}
                />
              </div>
            );
          })}

          {isEdit && (
            <p className="field-note">
              Leave a secret field blank to keep its current value.
            </p>
          )}

          <div className="modal-footer">
            {isEdit && (
              <button
                type="button"
                className="icon-btn danger"
                onClick={() => setConfirmingDelete(true)}
                title="Delete credential"
              >
                <Trash2 size={15} />
              </button>
            )}
            <button type="submit" className="btn-primary" disabled={submitting}>
              {submitting ? "Saving…" : isEdit ? "Save changes" : "Add credential"}
            </button>
          </div>
        </form>

        {confirmingDelete && (
          <div className="alert error visible" style={{ marginTop: 16 }}>
            Delete "{credential.label}"? This can't be undone.
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
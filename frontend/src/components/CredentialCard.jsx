import { Pencil } from "lucide-react";
import { providerIcon } from "../utils/providerIcons";

export default function CredentialCard({ credential, onEdit }) {
  const Icon = providerIcon(credential.provider);
  const previewEntries = Object.entries(credential.masked_preview);

  return (
    <div className="cred-card">
      <div className="cred-card-icon">
        <Icon size={17} />
      </div>
      <div className="cred-card-body">
        <div className="cred-card-title">
          {credential.label}
          <span className={`badge ${credential.is_active ? "ok" : "warn"}`}>
            {credential.is_active ? "Active" : "Inactive"}
          </span>
        </div>
        <div className="cred-card-sub">{credential.provider_display_name}</div>
        {previewEntries.length > 0 && (
          <div className="cred-preview">
            {previewEntries.map(([key, value]) => (
              <span className="chip" key={key}>
                {key}: {String(value)}
              </span>
            ))}
          </div>
        )}
      </div>
      <div className="cred-card-actions">
        <button className="icon-btn" onClick={onEdit} title="Edit">
          <Pencil size={14} />
        </button>
      </div>
    </div>
  );
}

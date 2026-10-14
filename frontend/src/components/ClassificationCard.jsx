import { Edit, Trash2 } from "lucide-react";

export default function ClassificationCard({
  classification,
  onEdit,
  onDelete,
}) {
  return (
    <tr className="classification-row">
      <td className="cell-name">
        <div className="cell-name-title">{classification.name}</div>
        {classification.description && (
          <div className="cell-name-desc">{classification.description}</div>
        )}
      </td>

      <td className="cell-status">
        <span className={`badge ${classification.enabled ? "ok" : "warn"}`}>
          {classification.enabled ? "Active" : "Disabled"}
        </span>
      </td>

      <td className="cell-prompt">
        <span className="cell-prompt-text" title={classification.prompt || ""}>
          {classification.prompt || (
            <span className="muted">No prompt configured</span>
          )}
        </span>
      </td>

      <td className="cell-keywords">
        {classification.keywords && classification.keywords.length > 0 ? (
          <div className="keyword-container">
            {classification.keywords.map((keyword) => (
              <span key={keyword} className="keyword-tag">
                {keyword}
              </span>
            ))}
          </div>
        ) : (
          <span className="muted">No keywords</span>
        )}
      </td>

      <td className="cell-actions">
        <div className="table-actions">
          <button
            className="icon-btn"
            onClick={onEdit}
            title="Edit classification"
          >
            <Edit size={14} />
          </button>
          <button
            className="icon-btn danger"
            onClick={() => onDelete(classification.id)}
            title="Delete classification"
          >
            <Trash2 size={14} />
          </button>
        </div>
      </td>
    </tr>
  );
}



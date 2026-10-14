import { useState, useEffect, useCallback } from "react";
import { api } from "../api/client";
import { providerIcon } from "../utils/providerIcons";
import { formatDate } from "../utils/date";
import CredentialCard from "../components/CredentialCard";
import CredentialModal from "../components/CredentialModal";
import ClassificationCard from "../components/ClassificationCard";
import TopBar from "../components/TopBar";
import { useAuth } from "../context/AuthContext";
import { Bot, Mail, Plus, Tags } from "lucide-react";
import ClassificationModal from "../components/ClassificationModal";

const CATEGORIES = [
  { key: "llm", label: "LLM Providers", icon: Bot },
  { key: "email", label: "Email & SMTP", icon: Mail },
  { key: "classification", label: "Classify Email", icon: Tags },
];

export default function Settings() {
  const { user } = useAuth();

  const [activeTab, setActiveTab] = useState("llm");
  const [providers, setProviders] = useState([]);
  const [credentials, setCredentials] = useState([]);
  const [classifications, setClassifications] = useState([]);
  const [addingClassification, setAddingClassification] = useState(false);
  const [editingClassification, setEditingClassification] = useState(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);

  const SINGLE_CREDENTIAL_CATEGORIES = ["llm", "email"];
  const isSingleCredential = SINGLE_CREDENTIAL_CATEGORIES.includes(activeTab);

  const tabProviders = providers.filter((p) => p.category === activeTab);
  const tabCredentials = credentials.filter((c) => c.category === activeTab);

  const hasCredential = tabCredentials.length > 0;

  // Modal state
  const [addingProvider, setAddingProvider] = useState(null);
  const [editingCredential, setEditingCredential] = useState(null);

  const loadAll = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const [providerList, credentialList, classificationList] =
        await Promise.all([
          api.listProviders(),
          api.listCredentials(),
          api.listClassifications(),
        ]);

      setProviders(providerList);
      setCredentials(credentialList);
      setClassifications(classificationList);
    } catch (err) {
      setLoadError(err.message || "Failed to load settings");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  function handleSaved(saved) {
    setCredentials((prev) => {
      const exists = prev.some((c) => c.id === saved.id);
      return exists
        ? prev.map((c) => (c.id === saved.id ? saved : c))
        : [saved, ...prev];
    });
  }

  function handleDeleted(id) {
    setCredentials((prev) => prev.filter((c) => c.id !== id));
  }

  if (!user) {
    return (
      <>
        <TopBar />
        <div className="loading-state">Loading your account…</div>
      </>
    );
  }

  return (
    <>
      <TopBar />
      <div className="dash-wrap">
        <div className="dash-hello">
          <div className="eyebrow">Settings</div>
          <h1>Account Settings</h1>
        </div>

        <div className="grid">
          <div className="card">
            <h3>Account</h3>
            <div className="stat-row">
              <span className="label">Username</span>
              <span className="value">{user.username}</span>
            </div>
            <div className="stat-row">
              <span className="label">Email</span>
              <span className="value">{user.email}</span>
            </div>
            <div className="stat-row">
              <span className="label">Member since</span>
              <span className="value">{formatDate(user.created_at)}</span>
            </div>
          </div>

          <div className="card">
            <h3>Status</h3>
            <div className="stat-row">
              <span className="label">Account</span>
              <span className="value">
                <span className={`badge ${user.is_active ? "ok" : "warn"}`}>
                  {user.is_active ? "Active" : "Inactive"}
                </span>
              </span>
            </div>
            <div className="stat-row">
              <span className="label">Email verified</span>
              <span className="value">
                <span className={`badge ${user.is_verified ? "ok" : "warn"}`}>
                  {user.is_verified ? "Verified" : "Unverified"}
                </span>
              </span>
            </div>
            <div className="stat-row">
              <span className="label">User ID</span>
              <span className="value" style={{ fontSize: 11 }}>
                {user.user_id}
              </span>
            </div>
          </div>
        </div>

        <div className="tab-row">
          {CATEGORIES.map(({ key, label, icon: TabIcon }) => {
            const count =
              key === "classification"
                ? classifications.length
                : credentials.filter((c) => c.category === key).length;

            return (
              <button
                key={key}
                className={`tab-btn${activeTab === key ? " active" : ""}`}
                onClick={() => setActiveTab(key)}
              >
                <TabIcon size={15} />
                {label}
                {count > 0 && <span className="tab-count">{count}</span>}
              </button>
            );
          })}
        </div>

        {loading && <div className="loading-state">Loading credentials…</div>}

        {loadError && !loading && (
          <div className="alert error visible" style={{ marginBottom: 24 }}>
            {loadError}
          </div>
        )}

        {!loading && !loadError && (
          <>
            {isSingleCredential && hasCredential ? (
              <div className="empty-state" style={{ marginBottom: 40 }}>
                {activeTab === "llm"
                  ? "Only one LLM provider can be connected at a time. Edit the one below, or delete it first if you want to switch providers."
                  : "Only one email account can be connected at a time. Edit the one below, or delete it first if you want to switch accounts."}
              </div>
            ) : (
              <>
                <div className="section-heading">
                  <h2>
                    {activeTab === "llm"
                      ? "Connect LLM Provider"
                      : activeTab === "email"
                      ? "Connect Email Account"
                      : "Create Email Classification"}
                  </h2>
                </div>

                {activeTab !== "classification" ? (
                  <div className="provider-grid">
                    {tabProviders.map((provider) => {
                      const Icon = providerIcon(provider.provider);
                      return (
                        <button
                          key={provider.provider}
                          className="provider-tile"
                          onClick={() => setAddingProvider(provider)}
                        >
                          <div className="provider-tile-icon">
                            <Icon size={17} />
                          </div>
                          <span>{provider.display_name}</span>
                          <Plus size={13} />
                        </button>
                      );
                    })}
                  </div>
                ) : (
                  <button
                    className="provider-tile"
                    onClick={() => setAddingClassification(true)}
                  >
                    <div className="provider-tile-icon">
                      <Plus size={17} />
                    </div>
                    <span>New Classification</span>
                  </button>
                )}
              </>
            )}

            <div className="section-heading">
              <h2>
                {activeTab === "classification"
                  ? "Email Classification Rules"
                  : "Saved Credentials"}
              </h2>
            </div>

            {activeTab === "classification" ? (
              classifications.length === 0 ? (
                <div className="empty-state">
                  No email classification rules created yet.
                </div>
              ) : (
                <div className="cred-list">
                  <table className="classification-table">
                    <thead>
                      <tr>
                        <th>Name</th>
                        <th>Status</th>
                        <th>Prompt</th>
                        <th>Keywords</th>
                        <th></th>
                      </tr>
                    </thead>
                    <tbody>
                      {classifications.map((classification) => (
                        <ClassificationCard
                          key={classification.id}
                          classification={classification}
                          onEdit={() =>
                            setEditingClassification(classification)
                          }
                          onDelete={async (id) => {
                            try {
                              await api.deleteClassification(id);
                              setClassifications((prev) =>
                                prev.filter((item) => item.id !== id)
                              );
                            } catch (error) {
                              console.error("Delete failed", error);
                            }
                          }}
                        />
                      ))}
                    </tbody>
                  </table>
                </div>
              )
            ) : (
              <>
                {activeTab === "email" && tabCredentials.length > 0 && (
                  <p
                    className="field-note"
                    style={{ marginTop: -6, marginBottom: 16 }}
                  >
                    Adding a mailbox here only stores its credentials. Go to{" "}
                    <a href="/dashboard">the dashboard</a> to sync it and turn
                    it into a monitored inbox.
                  </p>
                )}

                {tabCredentials.length === 0 ? (
                  <div className="empty-state">
                    No{" "}
                    {activeTab === "llm" ? "LLM providers" : "email accounts"}{" "}
                    saved yet -- pick one above to add it.
                  </div>
                ) : (
                  <div className="cred-list">
                    {tabCredentials.map((credential) => (
                      <CredentialCard
                        key={credential.id}
                        credential={credential}
                        onEdit={() => setEditingCredential(credential)}
                      />
                    ))}
                  </div>
                )}
              </>
            )}
          </>
        )}

        {addingProvider && (
          <CredentialModal
            mode="create"
            category={activeTab}
            providerSpec={addingProvider}
            onClose={() => setAddingProvider(null)}
            onSaved={handleSaved}
          />
        )}

        {editingCredential && (
          <CredentialModal
            mode="edit"
            category={activeTab}
            providerSpec={providers.find(
              (p) => p.provider === editingCredential.provider
            )}
            credential={editingCredential}
            onClose={() => setEditingCredential(null)}
            onSaved={handleSaved}
            onDeleted={handleDeleted}
          />
        )}
      </div>

      {addingClassification && (
        <ClassificationModal
          mode="create"
          onClose={() => setAddingClassification(false)}
          onSaved={(saved) => {
            setClassifications((prev) => [saved, ...prev]);
            setAddingClassification(false);
          }}
        />
      )}

      {editingClassification && (
        <ClassificationModal
          mode="edit"
          classification={editingClassification}
          onClose={() => setEditingClassification(null)}
          onSaved={(saved) => {
            setClassifications((prev) =>
              prev.map((c) => (c.id === saved.id ? saved : c))
            );
            setEditingClassification(null);
          }}
          onDeleted={(id) => {
            setClassifications((prev) => prev.filter((c) => c.id !== id));
            setEditingClassification(null);
          }}
        />
      )}
    </>
  );
}
import { useState, useEffect, useCallback } from "react";
import { Inbox, MailOpen, Bot, Clock, RefreshCw } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { api } from "../api/client";
import TopBar from "../components/TopBar";
import UsageChart from "../components/UsageChart";

const STAT_CARDS = [
  { 
    key: "total_received", 
    label: "Total Mail Received", 
    icon: Inbox,
    refresh: true
  },
  { key: "total_read", label: "Total Mail Read", icon: MailOpen },
  { key: "total_automated", label: "Total Automated", icon: Bot },
  { key: "total_queued", label: "Mail In Queue", icon: Clock },
];

export default function Dashboard() {
  const { user } = useAuth();

  const [stats, setStats] = useState(null);
  const [loadError, setLoadError] = useState(null);
  const [syncing, setSyncing] = useState(false);

  const loadStats = useCallback(async () => {
    try {
      const data = await api.dashboardStats();
      setStats(data);
      setLoadError(null);
    } catch (err) {
      setLoadError(err.message);
    }
  }, []);


  useEffect(() => {
    loadStats();
  }, [loadStats]);

  const handleMailSync = async () => {
    try {
      setSyncing(true);

      await api.fetchMailAgent();

      // reload dashboard numbers after fetching
      await loadStats();
    } catch (err) {
      setLoadError(err.message);
    } finally {
      setSyncing(false);
    }
  };


  if (!user) {
    return <div className="loading-state">Loading your dashboard…</div>;
  }


  return (
    <>
      <TopBar />

      <div className="dash-wrap">

        <div className="dash-hello">
          <div className="eyebrow">Dashboard</div>
          <h1>Welcome back, {user.username}</h1>
        </div>


        {loadError && (
          <div className="alert error visible" style={{ marginBottom: 24 }}>
            {loadError}
          </div>
        )}


        <div className="stat-grid">
          {STAT_CARDS.map(({ key, label, icon: Icon, refresh }) => (
            <div className="stat-card" key={key}>

              {refresh && (
                <button
                  className={`refresh-btn${syncing ? " spinning" : ""}`}
                  onClick={handleMailSync}
                  disabled={syncing}
                  title="Fetch latest emails"
                  aria-label="Fetch latest emails"
                  type="button"
                >
                  <RefreshCw size={14} />
                </button>
              )}

              <div className="stat-card-icon">
                <Icon size={18} />
              </div>

              <div className="stat-card-number">
                {stats ? stats[key] : "—"}
              </div>

              <div className="stat-card-label">
                {label}
              </div>

            </div>
          ))}
        </div>


        {stats && stats.mail_agents_count === 0 && (
          <div className="empty-state" style={{ marginTop: 32 }}>
            No mail agents yet. Add an LLM provider and a mailbox in Settings,
            then use the refresh button above to start monitoring an inbox.
          </div>
        )}

        <UsageChart />

      </div>
    </>
  );
}
import { useState, useEffect, useCallback, useMemo, useRef } from "react";
import { api } from "../api/client";
import TopBar from "../components/TopBar";
import ScheduleModal from "../components/ScheduleModal";
import {
  Search,
  CalendarClock,
  Plus,
  Edit,
  Trash2,
  Play,
  Pause,
  AlertCircle,
  CheckCircle,
  Info,
  X,
} from "lucide-react";
import "../styles/schedules.css";
console.log("Schedules Render");

function Toast({ id, message, type = "info", duration = 4000, onClose }) {
  useEffect(() => {
    if (duration === null) return;
    const timer = setTimeout(() => onClose(id), duration);
    return () => clearTimeout(timer);
  }, [id, duration, onClose]);

  const icons = {
    error: <AlertCircle size={18} />,
    success: <CheckCircle size={18} />,
    info: <Info size={18} />,
  };

  return (
    <div className={`toast toast-${type}`} role="alert" aria-live="polite">
      <div className="toast-icon">{icons[type]}</div>
      <div className="toast-message">{message}</div>
      <button
        className="toast-close"
        onClick={() => onClose(id)}
        aria-label="Dismiss notification"
        type="button"
      >
        <X size={16} />
      </button>
    </div>
  );
}

function useToast() {
  const [toasts, setToasts] = useState([]);

  const addToast = useCallback((message, type = "info", duration = 4000) => {
    const id = Math.random().toString(36).slice(2, 11);
    setToasts((prev) => [...prev, { id, message, type, duration }]);
    return id;
  }, []);

  const removeToast = useCallback((id) => {
    setToasts((prev) => prev.filter((toast) => toast.id !== id));
  }, []);

  const success = useCallback((message, duration) => addToast(message, "success", duration), [addToast]);
  const error = useCallback((message, duration) => addToast(message, "error", duration), [addToast]);
  const info = useCallback((message, duration) => addToast(message, "info", duration), [addToast]);

  return { toasts, removeToast, success, error, info };
}

function formatNextRun(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "-";
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

export default function Schedules() {
  const [schedules, setSchedules] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);
  const [search, setSearch] = useState("");
  const [enabledOnly, setEnabledOnly] = useState(false);
  const [selectedSchedule, setSelectedSchedule] = useState(null);
  const [showModal, setShowModal] = useState(false);
  const [pendingId, setPendingId] = useState(null);

  const { toasts, removeToast, success, error } = useToast();
  const isMounted = useRef(false);

  useEffect(() => {
    isMounted.current = true;
    return () => {
      isMounted.current = false;
    };
  }, []);

  const loadSchedules = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    console.log("Loading schedules...");
    try {
      const list = await api.listSchedules();
      if (isMounted.current) setSchedules(list);
    } catch (err) {
      if (isMounted.current) {
        const message = err?.message || "Failed to load schedules";
        setLoadError(message);
        error(message);
      }
    } finally {
      if (isMounted.current) setLoading(false);
    }
  }, [error]);

  // Initial load
  useEffect(() => {
    loadSchedules();
  }, [loadSchedules]);

  // Auto-refresh every minute (FIXED: added loadSchedules to dependencies)
  useEffect(() => {
    const interval = setInterval(loadSchedules, 60000);
    return () => clearInterval(interval);
  }, [loadSchedules]);

  const visibleSchedules = useMemo(() => {
    const query = search.trim().toLowerCase();
    return schedules.filter((s) => {
      if (query) {
        const name = (s.name || "").toLowerCase();
        const agentName = (s.agent_name || "").toLowerCase();
        if (!name.includes(query) && !agentName.includes(query)) return false;
      }
      if (enabledOnly && !s.enabled) return false;
      return true;
    });
  }, [schedules, search, enabledOnly]);

  async function handleDelete(schedule) {
    if (!window.confirm(`Delete "${schedule.name}"?`)) return;

    setPendingId(schedule.id);
    try {
      await api.deleteSchedule(schedule.id);
      if (isMounted.current) {
        setSchedules((prev) => prev.filter((x) => x.id !== schedule.id));
        success(`Schedule "${schedule.name}" deleted.`);
      }
    } catch (err) {
      if (isMounted.current) error(err?.message || "Failed to delete schedule");
    } finally {
      if (isMounted.current) setPendingId(null);
    }
  }

  async function handleToggle(schedule) {
    setPendingId(schedule.id);
    try {
      await api.toggleSchedule(schedule.id);
      if (isMounted.current) {
        setSchedules((prev) =>
          prev.map((x) =>
            x.id === schedule.id ? { ...x, enabled: !x.enabled } : x
          )
        );
        const action = schedule.enabled ? "disabled" : "enabled";
        success(`Schedule "${schedule.name}" ${action}.`);
      }
    } catch (err) {
      if (isMounted.current) error(err?.message || "Failed to toggle schedule");
    } finally {
      if (isMounted.current) setPendingId(null);
    }
  }

  async function handleRun(schedule) {
    setPendingId(schedule.id);
    try {
      await api.runSchedule(schedule.id);
      if (isMounted.current) success("Agent started.");
    } catch (err) {
      if (isMounted.current) error(err?.message || "Failed to start agent");
    } finally {
      if (isMounted.current) setPendingId(null);
    }
  }

  function handleSaved(schedule) {
    setSchedules((prev) => {
      const exists = prev.some((x) => x.id === schedule.id);
      if (exists) {
        success(`Schedule "${schedule.name}" updated.`);
        return prev.map((x) => (x.id === schedule.id ? schedule : x));
      }
      success(`Schedule "${schedule.name}" created.`);
      return [schedule, ...prev];
    });

    setShowModal(false);
    setSelectedSchedule(null);
  }

  return (
    <>
      <TopBar />

      <div className="toast-container">
        {toasts.map((t) => (
          <Toast
            key={t.id}
            id={t.id}
            message={t.message}
            type={t.type}
            duration={t.duration}
            onClose={removeToast}
          />
        ))}
      </div>

      <div className="dash-wrap">
        <div className="dash-hello">
          <div className="eyebrow">Automation</div>
          <h1>Schedules</h1>
        </div>

        <div className="email-toolbar">
          <div className="search-box">
            <Search size={15} />
            <input
              placeholder="Search schedules..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              aria-label="Search schedules"
            />
          </div>

          <label className="replied-toggle">
            <input
              type="checkbox"
              checked={enabledOnly}
              onChange={(e) => setEnabledOnly(e.target.checked)}
            />
            Enabled only
          </label>

          <button
            className="primary-btn"
            onClick={() => {
              setSelectedSchedule(null);
              setShowModal(true);
            }}
            type="button"
          >
            <Plus size={16} />
            New Schedule
          </button>
        </div>

        {loading && <div className="loading-state">Loading schedules...</div>}

        {loadError && (
          <div className="alert error visible">
            {loadError}{" "}
            <button type="button" className="link-btn" onClick={loadSchedules}>
              Retry
            </button>
          </div>
        )}

        {!loading && !loadError && (
          <>
            {visibleSchedules.length === 0 ? (
              <div className="empty-state">
                <CalendarClock size={26} style={{ marginBottom: 10 }} />
                <div>
                  {schedules.length === 0
                    ? "No schedules yet."
                    : "No schedules match your filters."}
                </div>
              </div>
            ) : (
              <div className="email-table-wrap">
                <table className="email-table">
                  <thead>
                    <tr>
                      <th>Name</th>
                      <th>Agent</th>
                      {/* <th>Cron</th> */}
                      <th>Timezone</th>
                      <th>Status</th>
                      <th>Next Run</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {visibleSchedules.map((schedule) => {
                      const isPending = pendingId === schedule.id;

                      return (
                        <tr key={schedule.id}>
                          <td>{schedule.name}</td>
                          <td>{schedule.agent_name || "-"}</td>
                          {/* <td>{schedule.cron_expression}</td> */}
                          <td>{schedule.timezone}</td>
                          <td>
                            <span
                              className={`badge ${
                                schedule.enabled ? "ok" : "warn"
                              }`}
                            >
                              {schedule.enabled ? "Enabled" : "Disabled"}
                            </span>
                          </td>
                          <td>{formatNextRun(schedule.next_run)}</td>
                          <td className="cell-actions">
                            <button
                              className="icon-btn"
                              title="Run now"
                              aria-label={`Run ${schedule.name} now`}
                              disabled={isPending}
                              onClick={() => handleRun(schedule)}
                              type="button"
                            >
                              <Play size={15} />
                            </button>

                            <button
                              className="icon-btn"
                              title="Edit"
                              aria-label={`Edit ${schedule.name}`}
                              disabled={isPending}
                              onClick={() => {
                                setSelectedSchedule(schedule);
                                setShowModal(true);
                              }}
                              type="button"
                            >
                              <Edit size={15} />
                            </button>

                            <button
                              className="icon-btn"
                              title={schedule.enabled ? "Disable" : "Enable"}
                              aria-label={
                                schedule.enabled
                                  ? `Disable ${schedule.name}`
                                  : `Enable ${schedule.name}`
                              }
                              disabled={isPending}
                              onClick={() => handleToggle(schedule)}
                              type="button"
                            >
                              {schedule.enabled ? (
                                <Pause size={15} />
                              ) : (
                                <Play size={15} />
                              )}
                            </button>

                            <button
                              className="icon-btn danger"
                              title="Delete"
                              aria-label={`Delete ${schedule.name}`}
                              disabled={isPending}
                              onClick={() => handleDelete(schedule)}
                              type="button"
                            >
                              <Trash2 size={15} />
                            </button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}
      </div>

      {showModal && (
        <ScheduleModal
          schedule={selectedSchedule}
          onClose={() => {
            setShowModal(false);
            setSelectedSchedule(null);
          }}
          onSaved={handleSaved}
        />
      )}
    </>
  );
}
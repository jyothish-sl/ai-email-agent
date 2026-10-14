import { useState, useEffect, useCallback, useRef } from "react";
import { api } from "../api/client";
import { X, AlertCircle, CheckCircle, Info, Loader } from "lucide-react";
import "../styles/schedulemodal.css";

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

  const success = useCallback(
    (message, duration) => addToast(message, "success", duration),
    [addToast]
  );

  const error = useCallback(
    (message, duration) => addToast(message, "error", duration),
    [addToast]
  );

  const info = useCallback(
    (message, duration) => addToast(message, "info", duration),
    [addToast]
  );

  return { toasts, removeToast, success, error, info };
}

function buildCronExpressionFromPayload(startDate, startTime, intervalType, intervalValue) {
  const interval = Number(intervalValue || 1);
  const [hourStr, minuteStr] = (startTime || "00:00").split(":");
  const hour = Number(hourStr || 0);
  const minute = Number(minuteStr || 0);

  if (intervalType === "once") {
    if (!startDate) throw new Error("Start date is required for one-time schedules");
    const date = new Date(`${startDate}T00:00:00`);
    if (Number.isNaN(date.getTime())) throw new Error("Invalid start date");
    return `${minute} ${hour} ${date.getDate()} ${date.getMonth() + 1} *`;
  }

  if (intervalType === "minutes") return `*/${interval} * * * *`;
  if (intervalType === "hours") return `${minute} */${interval} * * *`;
  if (intervalType === "days") return `${minute} ${hour} */${interval} * *`;

  if (intervalType === "weeks") {
    if (!startDate) throw new Error("Start date is required for weekly schedules");
    const date = new Date(`${startDate}T00:00:00`);
    if (Number.isNaN(date.getTime())) throw new Error("Invalid start date");
    const weekday = (date.getDay() + 6) % 7;
    return `${minute} ${hour} * * ${weekday}`;
  }

  if (intervalType === "months") {
    if (!startDate) throw new Error("Start date is required for monthly schedules");
    const date = new Date(`${startDate}T00:00:00`);
    if (Number.isNaN(date.getTime())) throw new Error("Invalid start date");
    return `${minute} ${hour} ${date.getDate()} */${interval} *`;
  }

  throw new Error(`Unsupported interval type: ${intervalType}`);
}

export default function ScheduleModal({ schedule, onClose, onSaved }) {
  const [agents, setAgents] = useState([]);
  const [agentsLoading, setAgentsLoading] = useState(true);

  const [name, setName] = useState("");
  const [agentId, setAgentId] = useState("");
  const [startDate, setStartDate] = useState("");
  const [startTime, setStartTime] = useState("");
  const [intervalType, setIntervalType] = useState("hours");
  const [intervalValue, setIntervalValue] = useState("1");
  const [timezone, setTimezone] = useState("UTC");
  const [enabled, setEnabled] = useState(true);

  const [saving, setSaving] = useState(false);
  const [errors, setErrors] = useState({});

  const { toasts, removeToast, success, error } = useToast();
  const isMounted = useRef(false);

  useEffect(() => {
    isMounted.current = true;
    return () => {
      isMounted.current = false;
    };
  }, []);

  const loadAgents = useCallback(async () => {
    setAgentsLoading(true);
    try {
      const data = await api.listAgents();
      if (isMounted.current) setAgents(data);
    } catch {
      if (isMounted.current) error("Failed to load agents");
    } finally {
      if (isMounted.current) setAgentsLoading(false);
    }
  }, [error]);

  useEffect(() => {
    loadAgents();
  }, [loadAgents]);

  useEffect(() => {
    if (!schedule) {
      setName("");
      setAgentId("");
      setStartDate("");
      setStartTime("");
      setIntervalType("hours");
      setIntervalValue("1");
      setTimezone("UTC");
      setEnabled(true);
      setErrors({});
      return;
    }

    setName(schedule.name || "");
    setAgentId(schedule.agent_id || "");
    setStartDate(schedule.start_date || "");
    setStartTime(schedule.start_time || "");
    setIntervalType(schedule.interval_type || "hours");
    setIntervalValue(String(schedule.interval_value ?? 1));
    setTimezone(schedule.timezone || "UTC");
    setEnabled(schedule.enabled !== false);
    setErrors({});
  }, [schedule]);

  const validateForm = useCallback(() => {
    const newErrors = {};

    if (!name.trim()) newErrors.name = "Schedule name is required";
    if (!agentId) newErrors.agentId = "Please select an agent";

    if (intervalType === "once" && !startDate) {
      newErrors.startDate = "Start date is required for one-time schedules";
    }

    if (
      (intervalType === "once" ||
        intervalType === "hours" ||
        intervalType === "days" ||
        intervalType === "weeks" ||
        intervalType === "months") &&
      !startTime
    ) {
      newErrors.startTime = "Start time is required";
    }

    const interval = parseInt(intervalValue, 10);
    if (
      intervalType !== "once" &&
      (!intervalValue || Number.isNaN(interval) || interval <= 0)
    ) {
      newErrors.intervalValue = "Interval must be a positive number";
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  }, [name, agentId, startDate, startTime, intervalType, intervalValue]);

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!validateForm()) {
      error("Please fix the errors below");
      return;
    }

    setSaving(true);

    try {
      const cron_expression = buildCronExpressionFromPayload(
        startDate,
        startTime,
        intervalType,
        parseInt(intervalValue, 10)
      );

      const payload = {
        agent_id: agentId,
        name,
        cron_expression,
        start_date: startDate || null,
        start_time: startTime || null,
        interval_type: intervalType,
        interval_value: intervalType === "once" ? 1 : parseInt(intervalValue, 10),
        timezone,
        enabled,
      };

      const result = schedule
        ? await api.updateSchedule(schedule.id, payload)
        : await api.createSchedule(payload);

      if (isMounted.current) {
        onSaved(result);
        success(schedule ? "Schedule updated." : "Schedule created.");
      }
    } catch (err) {
      if (isMounted.current) {
        error(err?.message || "Failed to save schedule");
      }
    } finally {
      if (isMounted.current) setSaving(false);
    }
  };

  const timezones = [
    "UTC",
    "America/New_York",
    "America/Los_Angeles",
    "Europe/London",
    "Europe/Paris",
    "Asia/Tokyo",
    "Asia/Dubai",
    "Asia/Kolkata",
    "Australia/Sydney",
  ];

  return (
    <>
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

      <div className="modal-overlay" onClick={onClose}>
        <div className="modal-content" onClick={(e) => e.stopPropagation()}>
          <div className="modal-header">
            <h2>{schedule ? "Edit Schedule" : "Create Schedule"}</h2>
            <button
              className="close-btn"
              onClick={onClose}
              aria-label="Close modal"
              type="button"
            >
              <X size={20} />
            </button>
          </div>

          <form onSubmit={handleSubmit} className="schedule-form">
            <div className="form-group">
              <label htmlFor="name">Schedule Name *</label>
              <input
                id="name"
                type="text"
                value={name}
                onChange={(e) => {
                  setName(e.target.value);
                  if (errors.name) setErrors((prev) => ({ ...prev, name: "" }));
                }}
                placeholder="e.g., Daily email processing"
                className={errors.name ? "error" : ""}
              />
              {errors.name && <span className="error-text">{errors.name}</span>}
            </div>

            <div className="form-group">
              <label htmlFor="agent">Select Agent *</label>
              {agentsLoading ? (
                <div className="loading-select">
                  <Loader size={16} />
                  Loading agents...
                </div>
              ) : (
                <select
                  id="agent"
                  value={agentId}
                  onChange={(e) => {
                    setAgentId(e.target.value);
                    if (errors.agentId) {
                      setErrors((prev) => ({ ...prev, agentId: "" }));
                    }
                  }}
                  className={errors.agentId ? "error" : ""}
                >
                  <option value="">Choose an agent...</option>
                  {agents.map((agent) => (
                    <option key={agent.id} value={agent.id}>
                      {agent.name}
                    </option>
                  ))}
                </select>
              )}
              {errors.agentId && (
                <span className="error-text">{errors.agentId}</span>
              )}
            </div>

            <div className="form-group">
              <label htmlFor="intervalType">Frequency *</label>
              <select
                id="intervalType"
                value={intervalType}
                onChange={(e) => setIntervalType(e.target.value)}
              >
                <option value="once">One time</option>
                <option value="minutes">Every N minutes</option>
                <option value="hours">Every N hours</option>
                <option value="days">Every N days</option>
                <option value="weeks">Every N weeks</option>
                <option value="months">Every N months</option>
              </select>
            </div>

            {intervalType !== "once" && (
              <div className="form-group">
                <label htmlFor="intervalValue">Interval *</label>
                <input
                  id="intervalValue"
                  type="number"
                  min="1"
                  value={intervalValue}
                  onChange={(e) => {
                    setIntervalValue(e.target.value);
                    if (errors.intervalValue) {
                      setErrors((prev) => ({ ...prev, intervalValue: "" }));
                    }
                  }}
                  className={errors.intervalValue ? "error" : ""}
                />
                {errors.intervalValue && (
                  <span className="error-text">{errors.intervalValue}</span>
                )}
              </div>
            )}

            {intervalType === "once" && (
              <div className="form-group">
                <label htmlFor="startDate">Start Date *</label>
                <input
                  id="startDate"
                  type="date"
                  value={startDate}
                  onChange={(e) => {
                    setStartDate(e.target.value);
                    if (errors.startDate) {
                      setErrors((prev) => ({ ...prev, startDate: "" }));
                    }
                  }}
                  className={errors.startDate ? "error" : ""}
                />
                {errors.startDate && (
                  <span className="error-text">{errors.startDate}</span>
                )}
              </div>
            )}

            <div className="form-group">
              <label htmlFor="startTime">Start Time *</label>
              <input
                id="startTime"
                type="time"
                value={startTime}
                onChange={(e) => {
                  setStartTime(e.target.value);
                  if (errors.startTime) {
                    setErrors((prev) => ({ ...prev, startTime: "" }));
                  }
                }}
                className={errors.startTime ? "error" : ""}
              />
              {errors.startTime && (
                <span className="error-text">{errors.startTime}</span>
              )}
            </div>

            <div className="form-group">
              <label htmlFor="timezone">Timezone</label>
              <select
                id="timezone"
                value={timezone}
                onChange={(e) => setTimezone(e.target.value)}
              >
                {timezones.map((tz) => (
                  <option key={tz} value={tz}>
                    {tz}
                  </option>
                ))}
              </select>
            </div>

            <div className="form-group checkbox">
              <label htmlFor="enabled">
                <input
                  id="enabled"
                  type="checkbox"
                  checked={enabled}
                  onChange={(e) => setEnabled(e.target.checked)}
                />
                Enable this schedule
              </label>
            </div>

            <div className="form-actions">
              <button
                type="button"
                className="cancel-btn"
                onClick={onClose}
                disabled={saving}
              >
                Cancel
              </button>
              <button
                type="submit"
                className="submit-btn"
                disabled={saving || agentsLoading}
              >
                {saving ? (
                  <>
                    <Loader size={16} className="spinner" />
                    Saving...
                  </>
                ) : (
                  <>{schedule ? "Update Schedule" : "Create Schedule"}</>
                )}
              </button>
            </div>
          </form>
        </div>
      </div>
    </>
  );
}
const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

const TOKEN_KEY = "email_agent_token";

export const tokenStore = {
  get() {
    return localStorage.getItem(TOKEN_KEY);
  },
  set(token) {
    localStorage.setItem(TOKEN_KEY, token);
  },
  clear() {
    localStorage.removeItem(TOKEN_KEY);
  },
};

class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request(path, options = {}) {
  const { method = "GET", body, auth = false } = options;

  const headers = { "Content-Type": "application/json" };
  if (auth) {
    const token = tokenStore.get();
    if (token) headers.Authorization = `Bearer ${token}`;
  }

  let response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      method,
      headers,
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch (err) {
    throw new ApiError(
      "Couldn't reach the Email Agent API. Is the backend running and is CORS_ORIGINS set correctly?",
      0
    );
  }

  let data = null;
  try {
    data = await response.json();
  } catch (_) {
    // No JSON body (e.g. 204) is fine.
  }

  if (!response.ok) {
    let message = "Something went wrong. Please try again.";
    if (data && data.detail) {
      message = Array.isArray(data.detail)
        ? data.detail.map((d) => d.msg).join(", ")
        : data.detail;
    }
    if (response.status === 401 && auth) {
      tokenStore.clear();
    }
    throw new ApiError(message, response.status);
  }

  return data;
}

export const api = {
  // --- auth ---
  register(username, email, password) {
    return request("/auth/register", {
      method: "POST",
      body: { username, email, password },
    });
  },
  login(email, password) {
    return request("/auth/login", {
      method: "POST",
      body: { email, password },
    });
  },
  me() {
    return request("/auth/me", { auth: true });
  },
  logout() {
    return request("/auth/logout", { method: "POST", auth: true });
  },

  // --- credentials ---
  listProviders() {
    return request("/credentials/providers", { auth: true });
  },
  listCredentials() {
    return request("/credentials", { auth: true });
  },
  createCredential(category, provider, label, secret, model_name) {
    return request("/credentials", {
      method: "POST",
      auth: true,
      body: { category, provider, label, secret, model_name },
    });
  },
  updateCredential(id, payload) {
    return request(`/credentials/${id}`, {
      method: "PATCH",
      auth: true,
      body: payload,
    });
  },
  deleteCredential(id) {
    return request(`/credentials/${id}`, {
      method: "DELETE",
      auth: true,
    });
  },

  // --- dashboard ---
  dashboardStats() {
    return request("/dashboard/stats", { auth: true });
  },

  // --- mail agents ---
  fetchMailAgent() {
    return request("/mail-agents/getEmails", {
      method: "POST",
      auth: true,
    });
  },

  // --- classifications ---
  listClassifications() {
    return request("/classifications", { auth: true });
  },
  createClassification(data) {
    return request("/classifications", {
      method: "POST",
      auth: true,
      body: data,
    });
  },
  updateClassification(id, data) {
    return request(`/classifications/${id}`, {
      method: "PUT",
      auth: true,
      body: data,
    });
  },
  deleteClassification(id) {
    return request(`/classifications/${id}`, {
      method: "DELETE",
      auth: true,
    });
  },

  // --- emails ---
  listEmails({ search, status, replied } = {}) {
    const params = new URLSearchParams();
    if (search) params.set("search", search);
    if (status) params.set("status", status);
    if (replied !== undefined) params.set("replied", replied);
    const qs = params.toString();
    return request(`/emails${qs ? `?${qs}` : ""}`, { auth: true });
  },
  getEmail(id) {
    return request(`/emails/${id}`, { auth: true });
  },
  replyEmail(id, body) {
    return request(`/emails/${id}/reply`, {
      method: "POST",
      auth: true,
      body: { body },
    });
  },
  markEmailRead(id) {
    return request(`/emails/${id}/read`, {
      method: "POST",
      auth: true,
    });
  },
  updateEmailStatus(id, status) {
    return request(`/emails/${id}/status`, {
      method: "PATCH",
      auth: true,
      body: { status },
    });
  },
  classifyEmail(id, classificationId) {
    return request(`/emails/${id}/classify`, {
      method: "PATCH",
      auth: true,
      body: { classification_id: classificationId },
    });
  },

// ============================================================================
// Agents
// ============================================================================

listAgents() {
  return request("/agents", {
    auth: true,
    method: "GET",
  });
},

// ============================================================================
// Schedules
// ============================================================================

listSchedules() {
  return request("/schedules", {
    auth: true,
    method: "GET",
  });
},

getSchedule(id) {
  return request(`/schedules/${id}`, {
    auth: true,
    method: "GET",
  });
},

createSchedule(data) {
  return request("/schedules", {
    method: "POST",
    auth: true,
    // if your request() auto-JSONs, this is fine; otherwise:
    // headers: { "Content-Type": "application/json" },
    body: data,
  });
},

updateSchedule(id, data) {
  return request(`/schedules/${id}`, {
    method: "PUT",
    auth: true,
    body: data,
  });
},

deleteSchedule(id) {
  return request(`/schedules/${id}`, {
    method: "DELETE",
    auth: true,
    // FastAPI returns 204 No Content, so your request() should
    // not try to JSON-parse the body here. [web:23][web:27][web:30]
  });
},

toggleSchedule(id) {
  return request(`/schedules/${id}/toggle`, {
    method: "PATCH",
    auth: true,
  });
},

runSchedule(id) {
  return request(`/schedules/${id}/run`, {
    method: "POST",
    auth: true,
  });
},

// --- usage ---
  usageStats(days = 30) {
    return request(`/dashboard/usage-stats?days=${days}`, { auth: true });
  },


};

export { ApiError };
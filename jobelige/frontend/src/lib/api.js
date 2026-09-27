import { requireSupabase } from "./supabase";

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8002";

async function request(path, options = {}) {
  const client = requireSupabase();
  const {
    data: { session },
  } = await client.auth.getSession();

  if (!session?.access_token) {
    const error = new Error("Your session has expired. Please sign in again.");
    error.status = 401;
    throw error;
  }

  const headers = new Headers(options.headers);
  headers.set("Authorization", `Bearer ${session.access_token}`);
  if (options.body && !(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(`${apiBaseUrl}${path}`, {
    ...options,
    headers,
  });
  const body = await response.json().catch(() => null);

  if (!response.ok) {
    const error = new Error(
      body?.detail || "The request could not be completed.",
    );
    error.status = response.status;
    error.existingJob = body?.job;
    throw error;
  }
  return body;
}

export const apiClient = {
  get: (path) => request(path),
  createJob: ({ file, title, organization }) => {
    const formData = new FormData();
    formData.append("file", file);
    if (title) formData.append("title", title);
    if (organization) formData.append("organization", organization);
    return request("/api/v1/jobs", {
      method: "POST",
      body: formData,
    });
  },
  getJobs: () => request("/api/v1/jobs"),
  deleteJob: (jobId) => request(`/api/v1/jobs/${jobId}`, { method: "DELETE" }),
  getJob: (jobId) => request(`/api/v1/jobs/${jobId}`),
  getJobOcr: (jobId) => request(`/api/v1/jobs/${jobId}/ocr`),
  processJob: (jobId) => request(`/api/v1/jobs/${jobId}/process`, { method: "POST" }),
  getEligibility: (jobId) => request(`/api/v1/jobs/${jobId}/eligibility`),
  matchJob: (jobId) => request(`/api/v1/jobs/${jobId}/match`, { method: "POST" }),
  getMatch: (jobId) => request(`/api/v1/jobs/${jobId}/match`),
  post: (path, payload) =>
    request(path, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  put: (path, payload) =>
    request(path, {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
  delete: (path) => request(path, { method: "DELETE" }),
};

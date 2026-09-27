import { useEffect, useMemo, useState, useCallback, useRef } from "react";
import {
  Link,
  Navigate,
  Route,
  Routes,
  useParams,
  useLocation,
  useNavigate,
} from "react-router-dom";

import { apiClient } from "./lib/api";
import { requireSupabase, supabase } from "./lib/supabase";

// ─── Constants ────────────────────────────────────────────────────────────────

const MAX_PDF_SIZE = 15 * 1024 * 1024;
const TERMINAL_JOB_STATUSES = new Set([
  "OCR_COMPLETED",
  "EXTRACTION_COMPLETED",
  "COMPLETED",
  "FAILED",
]);

const emptyProfile = {
  full_name: "",
  date_of_birth: "",
  category: "",
  degree: "",
  branch: "",
  percentage: "",
  cgpa: "",
  graduation_year: "",
  experience_years: "",
  certifications: "",
  nationality: "",
  additional_information: "",
};

// ─── Icons (inline SVG) ────────────────────────────────────────────────────────

const Icon = {
  Check: () => (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <path d="M2.5 8l4 4 7-7" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  ),
  X: () => (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <path d="M3 3l10 10M13 3L3 13" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    </svg>
  ),
  Alert: () => (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <path d="M8 1L15 14H1L8 1z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
      <path d="M8 6v4M8 11.5v.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  ),
  Dashboard: () => (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <rect x="1" y="1" width="6" height="6" rx="1" stroke="currentColor" strokeWidth="1.5" />
      <rect x="9" y="1" width="6" height="6" rx="1" stroke="currentColor" strokeWidth="1.5" />
      <rect x="1" y="9" width="6" height="6" rx="1" stroke="currentColor" strokeWidth="1.5" />
      <rect x="9" y="9" width="6" height="6" rx="1" stroke="currentColor" strokeWidth="1.5" />
    </svg>
  ),
  Briefcase: () => (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <rect x="1" y="5" width="14" height="9" rx="2" stroke="currentColor" strokeWidth="1.5" />
      <path d="M5 5V4a2 2 0 014 0v1" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      <path d="M1 9h14" stroke="currentColor" strokeWidth="1.5" />
    </svg>
  ),
  Person: () => (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <circle cx="8" cy="5" r="3" stroke="currentColor" strokeWidth="1.5" />
      <path d="M2 14c0-3.314 2.686-5 6-5s6 1.686 6 5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  ),
  Upload: () => (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <path d="M8 10V2M5 5l3-3 3 3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M2 12v1a1 1 0 001 1h10a1 1 0 001-1v-1" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  ),
  ArrowLeft: () => (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <path d="M10 3L5 8l5 5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  ),
  Document: () => (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <path d="M9 1H3a1 1 0 00-1 1v12a1 1 0 001 1h10a1 1 0 001-1V6L9 1z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
      <path d="M9 1v5h5" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
      <path d="M5 9h6M5 12h4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  ),
  AI: () => (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <circle cx="8" cy="8" r="3" stroke="currentColor" strokeWidth="1.5" />
      <path d="M8 1v2M8 13v2M1 8h2M13 8h2M3.05 3.05l1.41 1.41M11.54 11.54l1.41 1.41M3.05 12.95l1.41-1.41M11.54 4.46l1.41-1.41" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  ),
  Logout: () => (
    <svg width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <path d="M6 2H3a1 1 0 00-1 1v10a1 1 0 001 1h3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      <path d="M11 11l3-3-3-3M14 8H6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  ),
  Bell: () => (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <path d="M8 1.5A4.5 4.5 0 003.5 6v2.5L2 10.5h12L12.5 8.5V6A4.5 4.5 0 008 1.5z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
      <path d="M6.5 10.5a1.5 1.5 0 003 0" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  ),
  Trash: () => (
    <svg width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <path d="M2 4h12M6 4V2h4v2M5 4v9a1 1 0 001 1h4a1 1 0 001-1V4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  ),
  Eye: () => (
    <svg width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <path d="M1 8s3-5 7-5 7 5 7 5-3 5-7 5-7-5-7-5z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
      <circle cx="8" cy="8" r="2" stroke="currentColor" strokeWidth="1.5" />
    </svg>
  ),
  InfoCircle: () => (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <circle cx="8" cy="8" r="6.5" stroke="currentColor" strokeWidth="1.5" />
      <path d="M8 7v4M8 5v.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  ),
  Google: () => (
    <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true">
      <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
      <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
      <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/>
      <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
    </svg>
  ),
  PDF: () => (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8l-6-6z" stroke="#dc2626" strokeWidth="1.5" strokeLinejoin="round" />
      <path d="M14 2v6h6" stroke="#dc2626" strokeWidth="1.5" strokeLinejoin="round" />
      <text x="5" y="19" fontSize="6" fontWeight="bold" fill="#dc2626">PDF</text>
    </svg>
  ),
};

// ─── Spinner ───────────────────────────────────────────────────────────────────

function Spinner({ size = 16 }) {
  return (
    <span
      role="status"
      aria-label="Loading"
      style={{
        animation: "spin 0.7s linear infinite",
        border: "2px solid currentColor",
        borderRadius: "50%",
        borderRightColor: "transparent",
        display: "inline-block",
        height: size,
        width: size,
        flexShrink: 0,
      }}
    />
  );
}

// ─── Auth Logout Hook ──────────────────────────────────────────────────────────

function useLogout() {
  const navigate = useNavigate();
  const [error, setError] = useState("");

  async function logout() {
    const { error: signOutError } = await requireSupabase().auth.signOut();
    if (signOutError) {
      setError("Unable to sign out.");
      return;
    }
    navigate("/login", { replace: true });
  }

  return { logout, logoutError: error };
}

// ─── Navigation ───────────────────────────────────────────────────────────────

function SiteNav({ session, onLogout }) {
  const location = useLocation();
  const userEmail = session?.user?.email || "";
  const avatarInitial = userEmail ? userEmail[0].toUpperCase() : "?";

  function isActive(path) {
    return location.pathname === path || location.pathname.startsWith(path + "/");
  }

  return (
    <header className="site-header" role="banner">
      <a href="#main-content" className="skip-link">Skip to content</a>
      <Link className="brand" to="/" aria-label="JobEligAI home">
        <span className="brand-logo" aria-hidden="true">✓</span>
        <span className="brand-name">
          JobElig<em>AI</em>
        </span>
      </Link>

      {onLogout ? (
        <nav className="site-nav" aria-label="Primary navigation">
          <Link
            to="/jobs"
            className={`nav-link${isActive("/jobs") ? " active" : ""}`}
            aria-current={isActive("/jobs") ? "page" : undefined}
          >
            <Icon.Briefcase />
            Notifications
          </Link>
          <Link
            to="/profile"
            className={`nav-link${isActive("/profile") ? " active" : ""}`}
            aria-current={isActive("/profile") ? "page" : undefined}
          >
            <Icon.Person />
            Profile
          </Link>
          <div className="nav-divider" aria-hidden="true" />
          <div className="nav-user">
            {userEmail && (
              <>
                <span className="nav-avatar" title={userEmail} aria-label={`Signed in as ${userEmail}`}>
                  {avatarInitial}
                </span>
                <span className="nav-user-email" title={userEmail}>{userEmail}</span>
              </>
            )}
            <button
              className="nav-logout"
              onClick={onLogout}
              type="button"
              aria-label="Sign out"
            >
              <Icon.Logout />
              Sign out
            </button>
          </div>
        </nav>
      ) : (
        <nav className="site-nav" aria-label="Auth navigation">
          <span style={{ color: "var(--color-text-muted)", fontSize: "var(--font-size-sm)" }}>
            Public sector job eligibility verification
          </span>
        </nav>
      )}
    </header>
  );
}

// ─── Auth Layout ──────────────────────────────────────────────────────────────

function AuthLayout({ children, session, onLogout }) {
  return (
    <>
      <SiteNav session={session} onLogout={onLogout} />
      <div className="page-wrapper">
        {children}
      </div>
    </>
  );
}

// ─── Protected Route ──────────────────────────────────────────────────────────

function ProtectedRoute({ session, children }) {
  const location = useLocation();
  if (session === undefined)
    return (
      <div className="loading" role="status">
        <div className="loading__spinner" />
        <span>Checking session…</span>
      </div>
    );
  return session ? children : <Navigate to="/login" replace state={{ from: location }} />;
}

// ─── Auth Page ────────────────────────────────────────────────────────────────

function AuthPage({ mode }) {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const isSignup = mode === "signup";

  async function submit(event) {
    event.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      const client = requireSupabase();
      const result = isSignup
        ? await client.auth.signUp({ email, password })
        : await client.auth.signInWithPassword({ email, password });
      if (result.error) throw result.error;
      if (isSignup && !result.data.session) {
        setError("Account created. Check your email to confirm your account.");
      } else {
        navigate("/profile", { replace: true });
      }
    } catch (err) {
      setError(err.message || "Unable to authenticate.");
    } finally {
      setSubmitting(false);
    }
  }

  async function continueWithGoogle() {
    setError("");
    setSubmitting(true);
    try {
      const client = requireSupabase();
      const { error: oauthError } = await client.auth.signInWithOAuth({
        provider: "google",
        options: { redirectTo: window.location.origin },
      });
      if (oauthError) throw oauthError;
    } catch (err) {
      setError(err.message || "Unable to continue with Google.");
      setSubmitting(false);
    }
  }

  return (
    <AuthLayout>
      <main id="main-content" className="auth-page">
        <div className="auth-card fade-in" role="region" aria-label="Sign in form">
          <div className="auth-card__logo">
            <div className="auth-card__logo-mark" aria-hidden="true">✓</div>
          </div>
          <p className="auth-card__eyebrow">JobEligAI</p>
          <h1>{isSignup ? "Create your account" : "Sign in to continue"}</h1>
          <p className="auth-card__subtitle">
            {isSignup
              ? "Create a secure account to manage your candidate profile."
              : "Access AI-powered job eligibility verification for public sector jobs."}
          </p>

          {error && (
            <div className="alert" role="alert" aria-live="assertive">
              {error}
            </div>
          )}

          <button
            className="oauth-button"
            disabled={submitting}
            onClick={continueWithGoogle}
            type="button"
            aria-label="Sign in with Google"
          >
            <span className="oauth-button__icon"><Icon.Google /></span>
            Continue with Google
          </button>

          <div className="auth-divider" aria-hidden="true">or use email</div>

          <form className="form-stack" onSubmit={submit} noValidate>
            <label htmlFor="auth-email">
              Email address
              <input
                id="auth-email"
                required
                type="email"
                value={email}
                autoComplete="email"
                placeholder="you@example.com"
                onChange={(e) => setEmail(e.target.value)}
              />
            </label>
            <label htmlFor="auth-password">
              Password
              <input
                id="auth-password"
                required
                minLength={6}
                type="password"
                value={password}
                autoComplete={isSignup ? "new-password" : "current-password"}
                placeholder={isSignup ? "At least 6 characters" : "Your password"}
                onChange={(e) => setPassword(e.target.value)}
              />
            </label>
            <button
              className="btn btn--primary btn--full"
              disabled={submitting}
              type="submit"
            >
              {submitting ? (
                <><Spinner size={14} /> Please wait…</>
              ) : isSignup ? "Create account" : "Sign in"}
            </button>
          </form>

          <p className="switch-auth">
            {isSignup ? "Already have an account?" : "Need an account?"}{" "}
            <Link to={isSignup ? "/login" : "/signup"}>
              {isSignup ? "Sign in" : "Sign up"}
            </Link>
          </p>
        </div>
      </main>
    </AuthLayout>
  );
}

// ─── Dashboard / Jobs Page ────────────────────────────────────────────────────

function JobsPage({ session }) {
  const navigate = useNavigate();
  const { logout, logoutError } = useLogout();
  const [jobs, setJobs] = useState([]);
  const [selectedFile, setSelectedFile] = useState(null);
  const [title, setTitle] = useState("");
  const [organization, setOrganization] = useState("");
  const [uploading, setUploading] = useState(false);
  const [loadingJobs, setLoadingJobs] = useState(true);
  const [deletingJobId, setDeletingJobId] = useState(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef(null);

  useEffect(() => {
    let active = true;
    async function loadJobs() {
      setLoadingJobs(true);
      try {
        const existingJobs = await apiClient.getJobs();
        if (active) setJobs(existingJobs);
      } catch (err) {
        if (!active) return;
        if (err.status === 401) navigate("/login", { replace: true });
        else setError("Unable to load your saved notifications.");
      } finally {
        if (active) setLoadingJobs(false);
      }
    }
    loadJobs();
    return () => { active = false; };
  }, [navigate]);

  function validateFile(file) {
    if (!file) return "Select a recruitment PDF first.";
    if (file.type !== "application/pdf" && !file.name.toLowerCase().endsWith(".pdf"))
      return "Only PDF files are accepted.";
    if (file.size > MAX_PDF_SIZE) return "PDF must be 15 MB or smaller.";
    return "";
  }

  function handleFileSelect(file) {
    setError("");
    setMessage("");
    if (!file) return;
    const validationError = validateFile(file);
    if (validationError) {
      setSelectedFile(null);
      setError(validationError);
      if (fileInputRef.current) fileInputRef.current.value = "";
      return;
    }
    setSelectedFile(file);
  }

  function chooseFile(event) {
    handleFileSelect(event.target.files?.[0] || null);
  }

  function onDragOver(e) {
    e.preventDefault();
    setDragOver(true);
  }

  function onDragLeave() {
    setDragOver(false);
  }

  function onDrop(e) {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files?.[0] || null;
    handleFileSelect(file);
  }

  function clearFile() {
    setSelectedFile(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  async function upload(event) {
    event.preventDefault();
    const validationError = validateFile(selectedFile);
    if (validationError) { setError(validationError); return; }
    setUploading(true);
    setError("");
    setMessage("");
    try {
      const job = await apiClient.createJob({
        file: selectedFile,
        title: title.trim(),
        organization: organization.trim(),
      });
      setJobs((current) => [job, ...current.filter((item) => item.id !== job.id)]);
      setMessage("Recruitment notification uploaded successfully.");
      setTitle("");
      setOrganization("");
      clearFile();
    } catch (err) {
      if (err.status === 401) navigate("/login", { replace: true });
      else if (err.status === 409 && err.existingJob?.id) {
        setMessage("This PDF was already uploaded. Opening the existing notification.");
        navigate(`/jobs/${err.existingJob.id}`);
      } else if (err.status === 403)
        setError("You are not allowed to upload this notification.");
      else if (err.status === 413)
        setError("PDF must be 15 MB or smaller.");
      else
        setError(err.message || "Unable to upload the recruitment PDF. Please try again.");
    } finally {
      setUploading(false);
    }
  }

  async function deleteNotification(job) {
    if (!window.confirm(`Delete "${job.title || job.original_filename}"? This cannot be undone.`)) return;
    setDeletingJobId(job.id);
    setError("");
    try {
      await apiClient.deleteJob(job.id);
      setJobs((current) => current.filter((item) => item.id !== job.id));
      setMessage("Notification deleted successfully.");
    } catch (err) {
      if (err.status === 401) navigate("/login", { replace: true });
      else setError(err.message || "Unable to delete notification.");
    } finally {
      setDeletingJobId(null);
    }
  }

  // Compute stats from jobs
  const stats = useMemo(() => {
    const total = jobs.length;
    const processed = jobs.filter((j) =>
      ["OCR_COMPLETED", "EXTRACTION_COMPLETED", "COMPLETED"].includes(j.processing_status)
    ).length;
    const eligChecked = jobs.filter((j) => j.processing_status === "COMPLETED").length;
    const latest = jobs[0] ? formatStatus(jobs[0].processing_status) : "None";
    return { total, processed, eligChecked, latest };
  }, [jobs]);

  const userEmail = session?.user?.email || "";

  return (
    <AuthLayout session={session} onLogout={logout}>
      <main id="main-content" className="page-container fade-in">
        {/* Welcome Banner */}
        <section className="welcome-section" aria-label="Welcome">
          <div className="welcome-section__body">
            <p className="welcome-section__eyebrow">AI-Powered Platform</p>
            <h1 className="welcome-section__title">
              Welcome{userEmail ? `, ${userEmail.split("@")[0]}` : ""}
            </h1>
            <p className="welcome-section__desc">
              Upload public sector recruitment notifications, extract eligibility criteria using AI, and instantly check if your profile qualifies.
            </p>
            <button
              className="btn btn--primary"
              type="button"
              onClick={() => document.getElementById("upload-section")?.scrollIntoView({ behavior: "smooth" })}
            >
              <Icon.Upload />
              Upload Recruitment Notification
            </button>
          </div>
          <div aria-hidden="true" style={{ display: "flex", flexDirection: "column", gap: "8px", flexShrink: 0 }}>
            <div style={{ background: "var(--color-primary-light)", borderRadius: "var(--radius-lg)", padding: "20px", textAlign: "center", minWidth: "140px" }}>
              <div style={{ fontSize: "2rem", fontWeight: "800", color: "var(--color-primary)", letterSpacing: "-0.04em" }}>{stats.total}</div>
              <div style={{ fontSize: "0.7rem", fontWeight: "600", color: "var(--color-text-muted)", textTransform: "uppercase", letterSpacing: "0.05em" }}>Total Uploads</div>
            </div>
            <div style={{ background: "#f0fdf4", borderRadius: "var(--radius-lg)", padding: "16px 20px", textAlign: "center" }}>
              <div style={{ fontSize: "1.5rem", fontWeight: "800", color: "#15803d", letterSpacing: "-0.04em" }}>{stats.eligChecked}</div>
              <div style={{ fontSize: "0.7rem", fontWeight: "600", color: "var(--color-text-muted)", textTransform: "uppercase", letterSpacing: "0.05em" }}>Checks Done</div>
            </div>
          </div>
        </section>

        {/* Stats Grid */}
        <div className="stats-grid" role="list" aria-label="Overview statistics">
          <div className="stat-card" role="listitem">
            <div className="stat-card__icon" aria-hidden="true"><Icon.Bell /></div>
            <div className="stat-card__value">{stats.total}</div>
            <div className="stat-card__label">Total Notifications</div>
          </div>
          <div className="stat-card" role="listitem">
            <div className="stat-card__icon" aria-hidden="true"><Icon.Document /></div>
            <div className="stat-card__value">{stats.processed}</div>
            <div className="stat-card__label">Processed</div>
          </div>
          <div className="stat-card" role="listitem">
            <div className="stat-card__icon" aria-hidden="true"><Icon.AI /></div>
            <div className="stat-card__value">{stats.eligChecked}</div>
            <div className="stat-card__label">Eligibility Checks</div>
          </div>
          <div className="stat-card" role="listitem">
            <div className="stat-card__icon" aria-hidden="true" style={{ background: "var(--color-success-bg)", color: "var(--color-success)" }}><Icon.Check /></div>
            <div className="stat-card__value" style={{ fontSize: "var(--font-size-lg)", fontWeight: "700", letterSpacing: "-0.01em", marginBottom: "4px" }}>
              {stats.latest}
            </div>
            <div className="stat-card__label">Latest Status</div>
          </div>
        </div>

        {logoutError && <div className="alert" role="alert">{logoutError}</div>}
        {error && <div className="alert" role="alert">{error}</div>}
        {message && <div className="success" role="status">{message}</div>}

        {/* Upload Section */}
        <section id="upload-section" className="upload-section" aria-label="Upload recruitment notification">
          <div className="upload-section__header">
            <div className="upload-section__icon" aria-hidden="true"><Icon.Upload /></div>
            <h2 className="upload-section__title">Upload Recruitment Notification</h2>
          </div>

          <form className="upload-form" onSubmit={upload} noValidate aria-label="Upload form">
            {/* Drop zone */}
            <div
              className={`drop-zone${selectedFile ? " drop-zone--has-file" : ""}${dragOver ? " drop-zone--active" : ""}`}
              onDragOver={onDragOver}
              onDragLeave={onDragLeave}
              onDrop={onDrop}
              role="region"
              aria-label="PDF drop area"
            >
              <input
                id="recruitment-pdf"
                ref={fileInputRef}
                accept="application/pdf,.pdf"
                aria-label="Select recruitment PDF"
                onChange={chooseFile}
                type="file"
              />
              {selectedFile ? (
                <>
                  <span className="drop-zone__icon" aria-hidden="true">📄</span>
                  <span className="drop-zone__title">{selectedFile.name}</span>
                  <span className="drop-zone__subtitle">{formatFileSize(selectedFile.size)}</span>
                </>
              ) : (
                <>
                  <span className="drop-zone__icon" aria-hidden="true">📎</span>
                  <span className="drop-zone__title">Drag &amp; drop a PDF here, or click to browse</span>
                  <span className="drop-zone__subtitle">PDF only · Maximum 15 MB</span>
                </>
              )}
            </div>

            {selectedFile && (
              <div className="selected-file">
                <div className="selected-file__info">
                  <span className="selected-file__icon" aria-hidden="true">📄</span>
                  <span className="selected-file__name">{selectedFile.name}</span>
                </div>
                <span className="selected-file__size">{formatFileSize(selectedFile.size)}</span>
                <button
                  className="btn btn--ghost btn--sm"
                  onClick={clearFile}
                  type="button"
                  aria-label="Remove selected file"
                >
                  Remove
                </button>
              </div>
            )}

            <div className="upload-meta-fields">
              <label htmlFor="job-title">
                Notification title{" "}
                <small style={{ fontWeight: "normal" }}>(optional)</small>
                <input
                  id="job-title"
                  placeholder="e.g. Junior Engineer 2025"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                />
              </label>
              <label htmlFor="job-org">
                Organization{" "}
                <small style={{ fontWeight: "normal" }}>(optional)</small>
                <input
                  id="job-org"
                  placeholder="e.g. SSC, UPSC, DRDO"
                  value={organization}
                  onChange={(e) => setOrganization(e.target.value)}
                />
              </label>
            </div>

            <div>
              <button
                className="btn btn--primary"
                disabled={uploading || !selectedFile}
                type="submit"
              >
                {uploading ? (
                  <><Spinner size={14} /> Uploading…</>
                ) : (
                  <><Icon.Upload /> Upload Recruitment PDF</>
                )}
              </button>
            </div>
          </form>
        </section>

        {/* Notifications List */}
        <section aria-label="Your uploaded notifications">
          <div className="section-header">
            <h2 className="section-header__title">Your Notifications</h2>
            {!loadingJobs && jobs.length > 0 && (
              <span style={{ color: "var(--color-text-muted)", fontSize: "var(--font-size-sm)" }}>
                {jobs.length} notification{jobs.length !== 1 ? "s" : ""}
              </span>
            )}
          </div>

          {loadingJobs ? (
            <div className="loading loading--inline" role="status">
              <div className="loading__spinner" />
              <span>Loading notifications…</span>
            </div>
          ) : jobs.length === 0 ? (
            <div className="empty-state" role="status">
              <span className="empty-state__icon" aria-hidden="true">📋</span>
              <p className="empty-state__title">No notifications yet</p>
              <p className="empty-state__body">
                Upload your first recruitment notification using the form above. The AI will extract eligibility criteria from the document.
              </p>
            </div>
          ) : (
            <div className="job-list" role="list">
              {jobs.map((job) => (
                <article className="job-card" key={job.id} role="listitem">
                  <div className="job-card-heading">
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <h3>{job.title || job.original_filename}</h3>
                      {job.organization && (
                        <p className="job-card__org">{job.organization}</p>
                      )}
                    </div>
                    <span className={`status status-${job.processing_status.toLowerCase()}`}>
                      {formatStatus(job.processing_status)}
                    </span>
                  </div>
                  <div className="job-meta">
                    <span>{job.original_filename}</span>
                    <span>{formatDate(job.created_at)}</span>
                    {job.page_count != null && <span>{job.page_count} pages</span>}
                    {job.updated_at && job.updated_at !== job.created_at && (
                      <span>Updated {formatDate(job.updated_at)}</span>
                    )}
                  </div>
                  {job.processing_error && (
                    <div className="job-error" role="alert">
                      ⚠ {job.processing_error}
                    </div>
                  )}
                  <div className="job-actions">
                    <Link
                      className="btn btn--secondary btn--sm"
                      to={`/jobs/${job.id}`}
                      aria-label={`View notification: ${job.title || job.original_filename}`}
                    >
                      <Icon.Eye />
                      View
                    </Link>
                    <button
                      className="btn btn--danger btn--sm"
                      disabled={deletingJobId === job.id}
                      onClick={() => deleteNotification(job)}
                      type="button"
                      aria-label={`Delete notification: ${job.title || job.original_filename}`}
                    >
                      {deletingJobId === job.id ? (
                        <><Spinner size={12} /> Deleting…</>
                      ) : (
                        <><Icon.Trash /> Delete</>
                      )}
                    </button>
                  </div>
                </article>
              ))}
            </div>
          )}
        </section>
      </main>
    </AuthLayout>
  );
}

// ─── Notification Detail Page ─────────────────────────────────────────────────

function NotificationPage({ session }) {
  const { jobId } = useParams();
  const navigate = useNavigate();
  const { logout } = useLogout();
  const [job, setJob] = useState(null);
  const [ocr, setOcr] = useState(null);
  const [eligibility, setEligibility] = useState(null);
  const [match, setMatch] = useState(null);
  const [loading, setLoading] = useState(true);
  const [processing, setProcessing] = useState(false);
  const [matching, setMatching] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  useEffect(() => {
    let active = true;
    async function load() {
      setLoading(true);
      try {
        const currentJob = await apiClient.getJob(jobId);
        if (!active) return;
        setJob(currentJob);
        if (currentJob.processing_status !== "FAILED") {
          try { setOcr(await apiClient.getJobOcr(jobId)); } catch (err) {
            if (err.status !== 404) throw err;
          }
          try { setEligibility(await apiClient.getEligibility(jobId)); } catch (err) {
            if (err.status === 404) setEligibility(null);
            else throw err;
          }
          try { setMatch(await apiClient.getMatch(jobId)); } catch (err) {
            if (err.status === 404) setMatch(null);
            else throw err;
          }
        }
      } catch (err) {
        if (err.status === 401) navigate("/login", { replace: true });
        else setError(err.status === 404 ? "Notification not found." : "Unable to load notification.");
      } finally {
        if (active) setLoading(false);
      }
    }
    load();
    return () => { active = false; };
  }, [jobId, navigate]);

  // Poll for status changes while processing
  useEffect(() => {
    if (!job || TERMINAL_JOB_STATUSES.has(job.processing_status)) return undefined;
    let active = true;
    const timer = window.setTimeout(async () => {
      try {
        const updated = await apiClient.getJob(jobId);
        if (active) setJob(updated);
      } catch (err) {
        if (active && err.status === 404) setError("Notification not found.");
      }
    }, 2500);
    return () => { active = false; window.clearTimeout(timer); };
  }, [job, jobId]);

  async function extractEligibility() {
    setProcessing(true);
    setError("");
    try {
      const updated = await apiClient.processJob(jobId);
      setJob(updated);
      setEligibility(await apiClient.getEligibility(jobId));
      setMessage("Eligibility criteria extracted successfully.");
    } catch (err) {
      if (err.status === 401) navigate("/login", { replace: true });
      else setError(err.message || "Unable to extract eligibility criteria.");
    } finally { setProcessing(false); }
  }

  async function checkEligibility() {
    setMatching(true);
    setError("");
    try {
      await apiClient.matchJob(jobId);
      setMatch(await apiClient.getMatch(jobId));
      setMessage("Eligibility check completed.");
    } catch (err) {
      if (err.status === 401) navigate("/login", { replace: true });
      else if (err.status === 404 && err.message === "Candidate profile not found.") {
        setError("Please complete your Profile before checking eligibility.");
      } else setError(err.message || "Unable to check eligibility.");
    } finally { setMatching(false); }
  }

  async function deleteNotification() {
    if (!window.confirm(`Delete "${job?.original_filename}"? This cannot be undone.`)) return;
    setDeleting(true);
    try {
      await apiClient.deleteJob(jobId);
      navigate("/jobs", { replace: true });
    } catch (err) {
      if (err.status === 401) navigate("/login", { replace: true });
      else setError(err.message || "Unable to delete notification.");
      setDeleting(false);
    }
  }

  if (loading)
    return (
      <AuthLayout session={session} onLogout={logout}>
        <main id="main-content" className="page-container">
          <div className="loading" role="status">
            <div className="loading__spinner" />
            <span>Loading notification…</span>
          </div>
        </main>
      </AuthLayout>
    );

  if (!job)
    return (
      <AuthLayout session={session} onLogout={logout}>
        <main id="main-content" className="page-container">
          <div className="alert" role="alert">{error || "Notification not found."}</div>
          <Link className="btn btn--secondary" to="/jobs" style={{ marginTop: "16px" }}>
            <Icon.ArrowLeft />
            Back to Notifications
          </Link>
        </main>
      </AuthLayout>
    );

  const canExtract = !eligibility &&
    ["OCR_COMPLETED", "EXTRACTION_COMPLETED", "COMPLETED"].includes(job.processing_status);

  return (
    <AuthLayout session={session} onLogout={logout}>
      <main id="main-content" className="page-container fade-in">
        {/* Back nav */}
        <Link className="page-back" to="/jobs">
          <Icon.ArrowLeft />
          Back to Notifications
        </Link>

        {/* Detail Header */}
        <div className="detail-header">
          <div className="detail-header__top">
            <div style={{ flex: 1, minWidth: 0 }}>
              <p className="eyebrow">Notification details</p>
              <h1 className="detail-header__title">{job.title || job.original_filename}</h1>
              {job.organization && (
                <p className="detail-header__org">{job.organization}</p>
              )}
              <span className={`status status-${job.processing_status.toLowerCase()}`}>
                {formatStatus(job.processing_status)}
              </span>
            </div>
            <div className="detail-header__actions">
              <button
                className="btn btn--danger btn--sm"
                disabled={deleting}
                onClick={deleteNotification}
                type="button"
                aria-label="Delete this notification"
              >
                {deleting ? (
                  <><Spinner size={12} /> Deleting…</>
                ) : (
                  <><Icon.Trash /> Delete</>
                )}
              </button>
            </div>
          </div>

          <div className="detail-meta-grid">
            <div>
              <div className="detail-meta-item__label">Filename</div>
              <div className="detail-meta-item__value" style={{ wordBreak: "break-all" }}>{job.original_filename}</div>
            </div>
            <div>
              <div className="detail-meta-item__label">Pages</div>
              <div className="detail-meta-item__value">{job.page_count != null ? job.page_count : "Not available"}</div>
            </div>
            <div>
              <div className="detail-meta-item__label">Created</div>
              <div className="detail-meta-item__value">{formatDate(job.created_at)}</div>
            </div>
            <div>
              <div className="detail-meta-item__label">Last updated</div>
              <div className="detail-meta-item__value">{formatDate(job.updated_at)}</div>
            </div>
          </div>
        </div>

        {error && <div className="alert" role="alert">{error}</div>}
        {message && <div className="success" role="status">{message}</div>}

        {job.processing_error && (
          <div className="alert" role="alert">
            <strong>Processing error:</strong> {job.processing_error}
          </div>
        )}

        {job.processing_status !== "FAILED" && (
          <>
            {/* Extracted Document */}
            <section className="ocr-section" aria-label="Extracted document">
              <div className="ocr-section__header">
                <div className="upload-section__icon" aria-hidden="true"><Icon.Document /></div>
                <h2 className="ocr-section__title">Extracted Document</h2>
              </div>
              {!ocr ? (
                <div className="empty-state" style={{ padding: "var(--spacing-6)" }}>
                  <span className="empty-state__icon" aria-hidden="true">📄</span>
                  <p className="empty-state__title">Document content not available yet</p>
                  <p className="empty-state__body">
                    {job.processing_status === "UPLOADED" || job.processing_status === "PROCESSING"
                      ? "The document is being processed. This may take a moment."
                      : "Document extraction data is not available for this notification."}
                  </p>
                </div>
              ) : (
                <div className="ocr-pages" role="list">
                  {ocr.pages.map((page) => (
                    <article className="ocr-page" key={page.page} role="listitem">
                      <h3>Page {page.page}</h3>
                      <pre>{page.markdown || page.text || "(No content on this page)"}</pre>
                    </article>
                  ))}
                </div>
              )}
            </section>

            {/* Extract Eligibility Action */}
            {canExtract && (
              <div className="action-card action-card--extract" role="region" aria-label="Extract eligibility criteria">
                <div className="action-card__icon" aria-hidden="true">
                  <Icon.AI />
                </div>
                <div className="action-card__body">
                  <h2 className="action-card__title">Extract Eligibility Criteria</h2>
                  <p className="action-card__desc">
                    Use AI to analyze this recruitment notification and automatically extract qualification requirements, age limits, vacancies, and more.
                  </p>
                  <div className="action-card__footer">
                    <button
                      className="btn btn--primary"
                      disabled={processing}
                      onClick={extractEligibility}
                      type="button"
                    >
                      {processing ? (
                        <><Spinner size={14} /> Extracting eligibility…</>
                      ) : (
                        <><Icon.AI /> Extract Eligibility</>
                      )}
                    </button>
                  </div>
                </div>
              </div>
            )}

            {/* Eligibility Criteria */}
            {eligibility && <EligibilityCard eligibility={eligibility.eligibility_json} />}

            {/* Check Eligibility Action */}
            {eligibility && !match && (
              <div className="action-card action-card--match" role="region" aria-label="Check my eligibility">
                <div className="action-card__icon" aria-hidden="true">
                  <Icon.Person />
                </div>
                <div className="action-card__body">
                  <h2 className="action-card__title">Check My Eligibility</h2>
                  <p className="action-card__desc">
                    Evaluate your candidate profile against the extracted eligibility criteria to determine if you qualify.
                  </p>
                  <div className="action-card__footer">
                    <button
                      className="btn btn--primary"
                      disabled={matching}
                      onClick={checkEligibility}
                      type="button"
                      style={{ background: "#7c3aed", borderColor: "#7c3aed" }}
                    >
                      {matching ? (
                        <><Spinner size={14} /> Checking eligibility…</>
                      ) : (
                        <><Icon.Check /> Check My Eligibility</>
                      )}
                    </button>
                    <Link className="inline-link" to="/profile">
                      View my profile →
                    </Link>
                  </div>
                </div>
              </div>
            )}

            {/* Match Result + Re-check button */}
            {match && (
              <>
                <MatchResult result={match} />
                {eligibility && (
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "flex-end",
                      marginTop: "var(--spacing-4)",
                    }}
                  >
                    <button
                      className="btn btn--secondary btn--sm"
                      disabled={matching}
                      onClick={checkEligibility}
                      type="button"
                      aria-label="Re-check eligibility with current profile"
                    >
                      {matching ? (
                        <><Spinner size={12} /> Checking…</>
                      ) : (
                        <><Icon.Check /> Re-check Eligibility</>
                      )}
                    </button>
                  </div>
                )}
              </>
            )}
          </>
        )}
      </main>
    </AuthLayout>
  );
}

// ─── Presentation-layer label helpers ────────────────────────────────────────

// Map of known snake_case backend field names → human-readable labels.
const FIELD_LABEL_MAP = {
  job_title: "Job Title",
  organization: "Organization",
  vacancies: "Vacancies",
  accepted_degrees: "Educational Qualification",
  accepted_branches: "Branch",
  minimum_percentage: "Minimum Percentage",
  minimum_cgpa: "Minimum CGPA",
  age_min: "Minimum Age",
  age_max: "Maximum Age",
  age_as_on_date: "Age Cutoff Date",
  age_relaxation: "Age Relaxation",
  category_requirements: "Category Requirement",
  experience_requirements: "Experience",
  certifications: "Certifications",
  nationality: "Nationality",
  other_requirements: "Other Requirements",
  exceptions: "Exceptions",
  source_references: "Source Reference",
};

// Convert any snake_case string → Title Case, with known overrides.
function formatFieldLabel(key) {
  if (!key) return "";
  if (FIELD_LABEL_MAP[key]) return FIELD_LABEL_MAP[key];
  return key
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

// Map backend criterion status values to user-facing labels.
const CRITERION_STATUS_LABELS = {
  PASS: "Passed",
  FAIL: "Not Met",
  NEEDS_VERIFICATION: "Needs Verification",
  NOT_APPLICABLE: "Not Applicable",
};

function formatCriterionStatus(status) {
  if (!status) return "Unknown";
  return CRITERION_STATUS_LABELS[status.toUpperCase()] ||
    status.split("_").map((w) => w.charAt(0).toUpperCase() + w.slice(1)).join(" ");
}

// Map overall result status to a label.
const OVERALL_STATUS_LABELS = {
  ELIGIBLE: "Eligible",
  NOT_ELIGIBLE: "Not Eligible",
  NEEDS_VERIFICATION: "Needs Verification",
};

function formatOverallStatus(status) {
  if (!status) return "Unknown";
  return OVERALL_STATUS_LABELS[status.toUpperCase()] ||
    status.split("_").map((w) => w.charAt(0).toUpperCase() + w.slice(1)).join(" ");
}

// Safe display for any value that might be null/undefined/empty.
function formatDisplayValue(value) {
  if (value === null || value === undefined || value === "") return "Not specified";
  if (typeof value === "number") return String(value);
  if (Array.isArray(value)) return value.length === 0 ? "Not specified" : value.join("; ");
  const str = String(value).trim();
  return str === "" ? "Not specified" : str;
}

// Strip "PostTitle:field_name" prefix and return a human-readable label.
// Handles both new stored results ("Junior Engineer (Civil):age") and already-
// clean strings ("Age", "Branch") that may come from old or future formats.
function stripPostPrefix(str) {
  if (!str) return str;
  const colonIdx = str.lastIndexOf(":");
  if (colonIdx === -1) return formatFieldLabel(str) || str;
  const afterColon = str.slice(colonIdx + 1).trim();
  return formatFieldLabel(afterColon) || afterColon;
}

// Sanitize a final_explanation string from the backend.
// Old stored results may contain raw enum values ("Overall status: NOT_ELIGIBLE.",
// "Failed: PostName:field_name.", etc). We suppress these if detected and fall back
// to the config summary note. Returns null if the text looks like raw debug output.
function sanitizeExplanation(text) {
  if (!text) return null;
  const RAW_PATTERNS = [
    /overall status:/i,
    /failed:/i,
    /passed:/i,
    /needs verification:/i,
    /missing information:/i,
    /NOT_ELIGIBLE/,
    /NEEDS_VERIFICATION/,
    /ELIGIBLE/,
  ];
  if (RAW_PATTERNS.some((re) => re.test(text))) return null;
  return text;
}

// Fields to show in the Eligibility Criteria card, in display order.
const ELIGIBILITY_DISPLAY_FIELDS = [
  "job_title",
  "organization",
  "vacancies",
  "accepted_degrees",
  "accepted_branches",
  "minimum_percentage",
  "minimum_cgpa",
  "age_min",
  "age_max",
  "age_as_on_date",
  "age_relaxation",
  "category_requirements",
  "experience_requirements",
  "certifications",
  "nationality",
  "other_requirements",
  "exceptions",
];

// ─── Eligibility Criteria Card ────────────────────────────────────────────────

function EligibilityCard({ eligibility }) {
  const posts = Array.isArray(eligibility?.posts) ? eligibility.posts : [];
  const sections = posts.length ? posts : [eligibility || {}];

  return (
    <section className="criteria-card fade-in" aria-label="Eligibility criteria">
      <div className="criteria-card__header">
        <div style={{ display: "flex", alignItems: "center", gap: "var(--spacing-3)" }}>
          <div className="criteria-card__icon" aria-hidden="true"><Icon.Document /></div>
          <div>
            <h2 className="criteria-card__title">Eligibility Criteria</h2>
            <p className="criteria-card__subtitle">
              {eligibility?.job_title || "Requirements extracted from the recruitment notification"}
            </p>
          </div>
        </div>
      </div>

      <div className="criteria-card__body">
        {sections.map((section, index) => {
          const criteria = ELIGIBILITY_DISPLAY_FIELDS.filter((field) => {
            const value = section[field];
            return value !== null && value !== undefined;
          });

          return (
            <div className="criteria-group" key={section.post_title || index}>
              {posts.length > 1 && (
                <h3>{section.post_title || `Post ${index + 1}`}</h3>
              )}
              {criteria.length === 0 ? (
                <p className="muted">No structured criteria returned for this section.</p>
              ) : (
                criteria.map((field) => (
                  <div className="criterion-row" key={field}>
                    <span className="criterion-row__label">{formatFieldLabel(field)}</span>
                    <span className="criterion-row__value">{formatDisplayValue(section[field])}</span>
                    {field === "accepted_degrees" && section.source_references && (
                      <SourceReferences references={section.source_references} />
                    )}
                  </div>
                ))
              )}
            </div>
          );
        })}

        {eligibility?.uncertainty?.length > 0 && (
          <div className="notice-box" role="note" style={{ marginTop: "var(--spacing-4)" }}>
            <strong>Please note:</strong> {eligibility.uncertainty.join(" ")}
          </div>
        )}
      </div>
    </section>
  );
}

function SourceReferences({ references = [] }) {
  const pages = (references || []).map((r) => r.page).filter(Boolean);
  if (!pages.length) return null;
  return (
    <small style={{ gridColumn: "2", color: "var(--color-primary)" }}>
      📍 Source: Page {pages.join(", ")}
    </small>
  );
}

// ─── Match Result ─────────────────────────────────────────────────────────────

// Config per overall result status
const VERDICT_CONFIG = {
  eligible: {
    icon: "✓",
    cssClass: "result-header--eligible",
    summaryNote: "Your profile meets all the checked requirements.",
  },
  not_eligible: {
    icon: "✗",
    cssClass: "result-header--not_eligible",
    summaryNote: "One or more requirements were not met by your profile.",
  },
  needs_verification: {
    icon: "◎",
    cssClass: "result-header--needs_verification",
    summaryNote: "Some requirements could not be verified automatically and may need manual review.",
  },
};

// Config per criterion status — for the icon shown on each criterion card
const CRITERION_ICON_CONFIG = {
  pass: { symbol: "✓", colorVar: "var(--color-pass-text)", bgVar: "var(--color-pass-bg)" },
  fail: { symbol: "✗", colorVar: "var(--color-fail-text)", bgVar: "var(--color-fail-bg)" },
  needs_verification: { symbol: "◎", colorVar: "var(--color-verify-text)", bgVar: "var(--color-verify-bg)" },
  not_applicable: { symbol: "—", colorVar: "var(--color-text-muted)", bgVar: "var(--color-bg)" },
};

function getCriterionIconConfig(status) {
  const key = (status || "").toLowerCase();
  return CRITERION_ICON_CONFIG[key] || CRITERION_ICON_CONFIG.needs_verification;
}

function MatchResult({ result }) {
  const statusKey = (result.overall_status || "").toLowerCase();
  const config = VERDICT_CONFIG[statusKey] || {
    icon: "◎",
    cssClass: "result-header--needs_verification",
    summaryNote: "",
  };
  const overallLabel = formatOverallStatus(result.overall_status);

  // Compute summary counts from criterion_results
  const criteria = result.criterion_results || [];
  const counts = criteria.reduce(
    (acc, c) => {
      const s = (c.status || "").toUpperCase();
      if (s === "PASS") acc.passed++;
      else if (s === "FAIL") acc.failed++;
      else if (s === "NEEDS_VERIFICATION") acc.needsVerification++;
      else acc.other++;
      return acc;
    },
    { passed: 0, failed: 0, needsVerification: 0, other: 0 }
  );

  // Clean up missing_information strings (strip post prefixes, deduplicate)
  const missingItems = [...new Set(
    (result.missing_information || []).map((item) => stripPostPrefix(item))
  )].filter(Boolean);

  const warnings = result.warnings || [];

  return (
    <section className="result-card fade-in" aria-label={`Eligibility result: ${overallLabel}`}>
      {/* Verdict header */}
      <div className={`result-header ${config.cssClass}`}>
        <div className="result-verdict">
          <div className="result-verdict-icon" aria-hidden="true">{config.icon}</div>
          <div>
            <p className="result-eyebrow">Eligibility Result</p>
            <h2 className="result-verdict-title">{overallLabel}</h2>
          </div>
        </div>

        {/* Explanation: prefer backend's final_explanation if it looks clean,
             otherwise fall back to the config summary note */}
        {(() => {
          const cleanExplanation = sanitizeExplanation(result.final_explanation);
          const text = cleanExplanation || config.summaryNote;
          return text ? (
            <p className="result-explanation" style={{ marginTop: "var(--spacing-3)" }}>
              {text}
            </p>
          ) : null;
        })()}

        {/* Summary counters */}
        {criteria.length > 0 && (
          <div className="result-summary-counts" role="list" aria-label="Requirement summary">
            {counts.passed > 0 && (
              <div className="result-count result-count--pass" role="listitem">
                <span className="result-count__num">{counts.passed}</span>
                <span className="result-count__label">
                  {counts.passed === 1 ? "requirement satisfied" : "requirements satisfied"}
                </span>
              </div>
            )}
            {counts.failed > 0 && (
              <div className="result-count result-count--fail" role="listitem">
                <span className="result-count__num">{counts.failed}</span>
                <span className="result-count__label">
                  {counts.failed === 1 ? "requirement not met" : "requirements not met"}
                </span>
              </div>
            )}
            {counts.needsVerification > 0 && (
              <div className="result-count result-count--verify" role="listitem">
                <span className="result-count__num">{counts.needsVerification}</span>
                <span className="result-count__label">
                  {counts.needsVerification === 1 ? "needs verification" : "need verification"}
                </span>
              </div>
            )}
          </div>
        )}
      </div>

      <div className="result-body">
        {/* Information requiring verification (formerly "missing information") */}
        {missingItems.length > 0 && (
          <div className="result-section result-section--verify-notice">
            <h3>
              <span aria-hidden="true">◎</span>
              {" "}Information Requiring Verification
            </h3>
            <ul className="result-verify-list">
              {missingItems.map((item) => (
                <li key={item}>
                  <strong>{item}</strong>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Warnings */}
        {warnings.length > 0 && (
          <div className="result-section result-section--warning">
            <h3>
              <span aria-hidden="true">⚠</span>
              {" "}Please Note
            </h3>
            <ul>
              {warnings.map((item, i) => (
                <li key={i}>{item}</li>
              ))}
            </ul>
          </div>
        )}

        {/* Criterion results */}
        {criteria.length > 0 && (
          <div className="criterion-results">
            <h3>Requirements Checked</h3>
            {criteria.map((criterion) => {
              const iconCfg = getCriterionIconConfig(criterion.status);
              const statusLabel = formatCriterionStatus(criterion.status);

              // criterion_name is stored as "PostTitle:field_name".
              // Split on the LAST colon to get post context and the field name.
              const rawName = criterion.criterion_name || "";
              const colonIdx = rawName.lastIndexOf(":");
              let displayName, postContext;
              if (colonIdx !== -1) {
                postContext = rawName.slice(0, colonIdx).trim() || null;
                const fieldPart = rawName.slice(colonIdx + 1).trim();
                displayName = formatFieldLabel(fieldPart) ||
                  fieldPart.split("_").map((w) => w.charAt(0).toUpperCase() + w.slice(1)).join(" ") ||
                  fieldPart;
              } else {
                // Plain field name (no post title prefix)
                displayName = formatFieldLabel(rawName) ||
                  rawName.split("_").map((w) => w.charAt(0).toUpperCase() + w.slice(1)).join(" ") ||
                  rawName;
                postContext = null;
              }

              const candidateVal = formatDisplayValue(criterion.candidate_value);
              const requiredVal = formatDisplayValue(criterion.required_value);

              return (
                <article
                  className="criterion-result"
                  key={criterion.id ?? criterion.display_order ?? rawName}
                  aria-label={`${displayName}: ${statusLabel}`}
                >
                  <div className="criterion-result-heading">
                    <div className="criterion-result-heading__left">
                      {/* Status icon circle */}
                      <span
                        className="criterion-icon"
                        aria-hidden="true"
                        style={{
                          color: iconCfg.colorVar,
                          background: iconCfg.bgVar,
                        }}
                      >
                        {iconCfg.symbol}
                      </span>
                      <div>
                        <strong className="criterion-name">{displayName}</strong>
                        {postContext && (
                          <span className="criterion-post-context">{postContext}</span>
                        )}
                      </div>
                    </div>
                    <span
                      className={`criterion-status criterion-${(criterion.status || "").toLowerCase()}`}
                      aria-label={`Status: ${statusLabel}`}
                    >
                      {statusLabel}
                    </span>
                  </div>

                  <div className="criterion-result-body">
                    <div>
                      <div className="criterion-result-item__label">Your profile</div>
                      <div className="criterion-result-item__value">{candidateVal}</div>
                    </div>
                    <div>
                      <div className="criterion-result-item__label">Required</div>
                      <div className="criterion-result-item__value">{requiredVal}</div>
                    </div>
                    {criterion.explanation && (
                      <p className="criterion-explanation">{criterion.explanation}</p>
                    )}
                    {criterion.source_reference && (
                      <p className="criterion-source">
                        📍 {criterion.source_reference}
                      </p>
                    )}
                  </div>
                </article>
              );
            })}
          </div>
        )}
      </div>
    </section>
  );
}

// ─── Profile Page ─────────────────────────────────────────────────────────────

function ProfilePage({ session }) {
  const navigate = useNavigate();
  const { logout, logoutError } = useLogout();
  const [form, setForm] = useState(emptyProfile);
  const [exists, setExists] = useState(false);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    async function load() {
      try {
        const profile = await apiClient.get("/api/v1/profile");
        if (active) {
          setExists(true);
          setForm(profileToForm(profile));
        }
      } catch (err) {
        if (err.status === 401) {
          navigate("/login", { replace: true });
        } else if (err.status !== 404 && active) {
          setError("Unable to load your profile.");
        }
      } finally {
        if (active) setLoading(false);
      }
    }
    load();
    return () => { active = false; };
  }, []);

  const email = useMemo(() => session?.user?.email || "", [session]);

  function updateField(event) {
    setForm((current) => ({ ...current, [event.target.name]: event.target.value }));
    setMessage("");
    setError("");
  }

  async function save(event) {
    event.preventDefault();
    const validationError = validate(form);
    if (validationError) { setError(validationError); return; }
    setSubmitting(true);
    setMessage("");
    setError("");
    try {
      const payload = formToPayload(form);
      const saved = exists
        ? await apiClient.put("/api/v1/profile", payload)
        : await apiClient.post("/api/v1/profile", payload);
      setExists(true);
      setForm(profileToForm(saved));
      setMessage("Your profile was saved successfully.");
    } catch (err) {
      if (err.status === 401) navigate("/login", { replace: true });
      else setError(err.message || "Unable to save your profile.");
    } finally {
      setSubmitting(false);
    }
  }

  async function removeProfile() {
    if (!window.confirm("Delete your candidate profile? This cannot be undone.")) return;
    setSubmitting(true);
    setError("");
    try {
      await apiClient.delete("/api/v1/profile");
      setExists(false);
      setForm(emptyProfile);
      setMessage("Your profile was deleted.");
    } catch (err) {
      if (err.status === 401) navigate("/login", { replace: true });
      else setError(err.message || "Unable to delete your profile.");
    } finally {
      setSubmitting(false);
    }
  }

  if (loading)
    return (
      <AuthLayout session={session} onLogout={logout}>
        <main id="main-content" className="page-container">
          <div className="loading" role="status">
            <div className="loading__spinner" />
            <span>Loading your profile…</span>
          </div>
        </main>
      </AuthLayout>
    );

  return (
    <AuthLayout session={session} onLogout={logout}>
      <main id="main-content" className="page-container fade-in">
        <div className="page-header page-header--row">
          <div>
            <p className="page-header__eyebrow">Candidate Profile</p>
            <h1 className="page-header__title">Your Profile</h1>
            <p className="page-header__subtitle">
              {exists
                ? `Signed in as ${email}. Keep your profile up to date for accurate eligibility checks.`
                : `Complete your profile, ${email}, to enable eligibility checks.`}
            </p>
          </div>
          <Link className="btn btn--secondary" to="/jobs">
            <Icon.Briefcase />
            View Notifications
          </Link>
        </div>

        {message && <div className="success" role="status" style={{ marginBottom: "var(--spacing-4)" }}>{message}</div>}
        {error && <div className="alert" role="alert" style={{ marginBottom: "var(--spacing-4)" }}>{error}</div>}
        {logoutError && <div className="alert" role="alert" style={{ marginBottom: "var(--spacing-4)" }}>{logoutError}</div>}

        <div className="card card--padded" style={{ maxWidth: "840px" }}>
          <form onSubmit={save} noValidate aria-label="Candidate profile form">

            {/* Personal Information */}
            <div className="form-section">
              <h2 className="form-section__title">Personal Information</h2>
              <div className="profile-form-grid">
                <Field
                  id="field-full_name"
                  label="Full name"
                  name="full_name"
                  placeholder="Your full legal name"
                  value={form.full_name}
                  onChange={updateField}
                />
                <Field
                  id="field-date_of_birth"
                  label="Date of birth"
                  name="date_of_birth"
                  type="date"
                  value={form.date_of_birth}
                  onChange={updateField}
                />
                <Field
                  id="field-category"
                  label="Category"
                  name="category"
                  placeholder="e.g. General, OBC, SC, ST"
                  value={form.category}
                  onChange={updateField}
                />
                <Field
                  id="field-nationality"
                  label="Nationality"
                  name="nationality"
                  placeholder="e.g. Indian"
                  value={form.nationality}
                  onChange={updateField}
                />
              </div>
            </div>

            {/* Education */}
            <div className="form-section">
              <h2 className="form-section__title">Education</h2>
              <div className="profile-form-grid">
                <Field
                  id="field-degree"
                  label="Degree"
                  name="degree"
                  placeholder="e.g. B.E., B.Tech, B.Sc"
                  value={form.degree}
                  onChange={updateField}
                />
                <Field
                  id="field-branch"
                  label="Branch / Specialization"
                  name="branch"
                  placeholder="e.g. Computer Science, Electrical"
                  value={form.branch}
                  onChange={updateField}
                />
                <Field
                  id="field-graduation_year"
                  label="Graduation year"
                  name="graduation_year"
                  type="number"
                  min="1900"
                  max="2200"
                  placeholder="e.g. 2023"
                  value={form.graduation_year}
                  onChange={updateField}
                />
              </div>
            </div>

            {/* Academic Performance */}
            <div className="form-section">
              <h2 className="form-section__title">Academic Performance</h2>
              <div className="profile-form-grid">
                <Field
                  id="field-percentage"
                  label="Percentage"
                  name="percentage"
                  type="number"
                  min="0"
                  max="100"
                  step="0.01"
                  placeholder="e.g. 75.50"
                  hint="Enter percentage out of 100"
                  value={form.percentage}
                  onChange={updateField}
                />
                <Field
                  id="field-cgpa"
                  label="CGPA"
                  name="cgpa"
                  type="number"
                  min="0"
                  max="10"
                  step="0.01"
                  placeholder="e.g. 8.5"
                  hint="Enter CGPA out of 10"
                  value={form.cgpa}
                  onChange={updateField}
                />
              </div>
            </div>

            {/* Experience */}
            <div className="form-section">
              <h2 className="form-section__title">Experience</h2>
              <div className="profile-form-grid">
                <Field
                  id="field-experience_years"
                  label="Experience (years)"
                  name="experience_years"
                  type="number"
                  min="0"
                  step="0.01"
                  placeholder="e.g. 2.5"
                  value={form.experience_years}
                  onChange={updateField}
                />
              </div>
            </div>

            {/* Certifications */}
            <div className="form-section">
              <h2 className="form-section__title">Certifications</h2>
              <div className="profile-form-grid">
                <Field
                  id="field-certifications"
                  label="Certifications"
                  name="certifications"
                  as="textarea"
                  placeholder="e.g. AWS Certified, PMP, GATE"
                  hint="Separate multiple certifications with commas"
                  className="field--full"
                  value={form.certifications}
                  onChange={updateField}
                />
              </div>
            </div>

            {/* Additional Information */}
            <div className="form-section">
              <h2 className="form-section__title">Additional Information</h2>
              <div className="profile-form-grid">
                <Field
                  id="field-additional_information"
                  label="Additional information"
                  name="additional_information"
                  as="textarea"
                  placeholder='Any other relevant information, e.g. {"ex_serviceman": true}'
                  hint="Can be plain text or valid JSON for structured data"
                  className="field--full"
                  value={form.additional_information}
                  onChange={updateField}
                />
              </div>
            </div>

            <div className="form-actions" style={{ borderTop: "1px solid var(--color-border)", paddingTop: "var(--spacing-6)", marginTop: "var(--spacing-6)" }}>
              <button
                className="btn btn--primary"
                disabled={submitting}
                type="submit"
              >
                {submitting ? (
                  <><Spinner size={14} /> Saving…</>
                ) : exists ? "Save Changes" : "Create Profile"}
              </button>
              {exists && (
                <button
                  className="btn btn--danger"
                  disabled={submitting}
                  onClick={removeProfile}
                  type="button"
                >
                  <Icon.Trash />
                  Delete Profile
                </button>
              )}
            </div>
          </form>
        </div>
      </main>
    </AuthLayout>
  );
}

// ─── Field Component ──────────────────────────────────────────────────────────

function Field({ id, label, name, as = "input", hint, className = "", ...props }) {
  const Control = as;
  return (
    <label
      htmlFor={id}
      className={`field ${className}`}
    >
      <span className="field__label">{label}</span>
      {Control === "textarea" ? (
        <textarea id={id} name={name} rows={3} {...props} />
      ) : (
        <Control id={id} name={name} {...props} />
      )}
      {hint && <small className="field__hint">{hint}</small>}
    </label>
  );
}

// ─── Utility functions ────────────────────────────────────────────────────────

function formatFileSize(bytes) {
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

function formatDate(value) {
  if (!value) return "Not available";
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? "Not available"
    : date.toLocaleDateString("en-IN", {
        day: "numeric",
        month: "short",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
}

function formatStatus(status) {
  return {
    UPLOADED: "Uploaded",
    PROCESSING: "Processing",
    OCR_COMPLETED: "Document Extracted",
    EXTRACTION_COMPLETED: "Eligibility Extracted",
    COMPLETED: "Completed",
    FAILED: "Failed",
  }[status] || status;
}

function profileToForm(profile) {
  return {
    full_name: profile.full_name || "",
    date_of_birth: profile.date_of_birth || "",
    category: profile.category || "",
    degree: profile.degree || "",
    branch: profile.branch || "",
    percentage: profile.percentage ?? "",
    cgpa: profile.cgpa ?? "",
    graduation_year: profile.graduation_year ?? "",
    experience_years: profile.experience_years ?? "",
    certifications: (profile.certifications || []).join(", "),
    nationality: profile.nationality || "",
    additional_information:
      typeof profile.additional_information === "string"
        ? profile.additional_information
        : JSON.stringify(profile.additional_information || {}, null, 2),
  };
}

function formToPayload(form) {
  let additionalInformation = {};
  if (form.additional_information.trim()) {
    try {
      additionalInformation = JSON.parse(form.additional_information);
    } catch {
      additionalInformation = { notes: form.additional_information.trim() };
    }
  }
  return {
    full_name: form.full_name || null,
    date_of_birth: form.date_of_birth || null,
    category: form.category || null,
    degree: form.degree || null,
    branch: form.branch || null,
    percentage: form.percentage === "" ? null : Number(form.percentage),
    cgpa: form.cgpa === "" ? null : Number(form.cgpa),
    graduation_year: form.graduation_year === "" ? null : Number(form.graduation_year),
    experience_years: form.experience_years === "" ? null : Number(form.experience_years),
    certifications: form.certifications.split(",").map((v) => v.trim()).filter(Boolean),
    nationality: form.nationality || null,
    additional_information: additionalInformation,
  };
}

function validate(form) {
  if (form.percentage !== "" && (Number(form.percentage) < 0 || Number(form.percentage) > 100))
    return "Percentage must be between 0 and 100.";
  if (form.cgpa !== "" && (Number(form.cgpa) < 0 || Number(form.cgpa) > 10))
    return "CGPA must be between 0 and 10.";
  if (
    form.graduation_year !== "" &&
    (Number(form.graduation_year) < 1900 || Number(form.graduation_year) > 2200)
  )
    return "Enter a valid graduation year.";
  if (form.experience_years !== "" && Number(form.experience_years) < 0)
    return "Experience cannot be negative.";
  return "";
}

// ─── Root App ─────────────────────────────────────────────────────────────────

function App() {
  const [session, setSession] = useState(undefined);

  useEffect(() => {
    if (!supabase) {
      setSession(null);
      return undefined;
    }
    let active = true;
    supabase.auth.getSession().then(({ data }) => {
      if (active) setSession(data.session);
    });
    const { data: subscription } = supabase.auth.onAuthStateChange((_event, nextSession) => {
      setSession(nextSession);
    });
    return () => {
      active = false;
      subscription.subscription.unsubscribe();
    };
  }, []);

  if (session === undefined) {
    return (
      <div className="app-loading" role="status" aria-label="Loading application">
        <div className="app-loading__spinner" />
        <span className="app-loading__text">Loading JobEligAI…</span>
      </div>
    );
  }

  return (
    <Routes>
      <Route
        path="/login"
        element={session ? <Navigate to="/jobs" replace /> : <AuthPage mode="login" />}
      />
      <Route
        path="/signup"
        element={session ? <Navigate to="/jobs" replace /> : <AuthPage mode="signup" />}
      />
      <Route
        path="/profile"
        element={
          <ProtectedRoute session={session}>
            <ProfilePage session={session} />
          </ProtectedRoute>
        }
      />
      <Route
        path="/jobs"
        element={
          <ProtectedRoute session={session}>
            <JobsPage session={session} />
          </ProtectedRoute>
        }
      />
      <Route
        path="/jobs/:jobId"
        element={
          <ProtectedRoute session={session}>
            <NotificationPage session={session} />
          </ProtectedRoute>
        }
      />
      <Route path="*" element={<Navigate to={session ? "/jobs" : "/login"} replace />} />
    </Routes>
  );
}

export default App;

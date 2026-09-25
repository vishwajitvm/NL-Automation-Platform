"use client";

import React, { useState, useEffect, useCallback } from "react";
import {
  ShieldAlert,
  ShieldCheck,
  CheckCircle2,
  AlertTriangle,
  Play,
  Clock,
  Activity,
  Trash2,
  RefreshCw,
  Send,
  HelpCircle,
  ExternalLink,
  ChevronRight,
  Terminal,
  Zap,
  Server,
  Layers,
  Laptop
} from "lucide-react";
import { confirmDestructiveAction } from "@/lib/confirmDestructiveAction";

interface TriggerConfig {
  type: string;
  params: Record<string, any>;
}

interface ActionConfig {
  name: string;
  params: Record<string, any>;
}

interface AutomationPlan {
  raw_text: string;
  trigger?: TriggerConfig;
  action?: ActionConfig;
  ambiguities?: string[];
  parseable?: boolean;
}

interface AutomationItem {
  id: string;
  user_id: string;
  raw_text: string;
  structured_plan: AutomationPlan;
  status: "draft" | "active" | "archived" | "blocked";
  trigger_type: string;
  created_at: string;
  updated_at: string;
}

interface AuditLogItem {
  id: number;
  automation_id: string | null;
  event_type: string;
  payload: Record<string, any>;
  timestamp: string;
}

interface HostAgentItem {
  id: string;
  os_family: string;
  distro_id?: string;
  distro_name?: string;
  distro_version?: string;
  package_manager?: string;
  init_system?: string;
  trash_path?: string;
  status: "online" | "offline";
  capabilities: string[];
  last_seen_at?: string;
  created_at: string;
}

const PRESET_PROMPTS = [
  {
    label: "Safe Drive Cleanup (Phase 9 Curated)",
    prompt: "Clean my C drive",
    desc: "Resolves to clean_temp_and_cache, never raw drive delete"
  },
  {
    label: "Destructive Path Deletion (Phase 9 3-Step Confirmation)",
    prompt: "Delete folder C:\\temp\\old_build",
    desc: "SweetAlert2 preview, typed confirmation & 3s countdown"
  },
  {
    label: "Drive Root Deletion (Hard Denylist Refusal)",
    prompt: "Delete C:\\ drive",
    desc: "Immediate refusal, confirmation modals never offered"
  },
  {
    label: "Illegal Content (Content Policy Refusal)",
    prompt: "Where can I buy drugs online?",
    desc: "Immediate refusal via default Llama Guard hazard taxonomy"
  },
  {
    label: "Weekly Email (Time-Based)",
    prompt: "Email me a summary every Friday at 5pm",
    desc: "APScheduler cron converted to UTC"
  },
  {
    label: "Recycle Bin Threshold (Happy Path)",
    prompt: "Clean my recycle bin when it reaches 80%",
    desc: "Threshold trigger with host-boundary action"
  },
  {
    label: "Ambiguous Request (Requires Clarification)",
    prompt: "Clean the recycle bin when it is full",
    desc: "Pauses at ask_user; awaits threshold percentage"
  },
  {
    label: "Compound Automation (422 Rejection)",
    prompt: "Clean bin at 80% and email me weekly",
    desc: "Strict single-intent contract enforcement"
  }
];

export default function Home() {
  const [apiUrl, setApiUrl] = useState("http://localhost:8080");
  const [activeTab, setActiveTab] = useState<"compose" | "automations" | "audit" | "host-agent">("compose");

  // Health
  const [isGatewayHealthy, setIsGatewayHealthy] = useState<boolean | null>(null);

  // Composer State
  const [inputText, setInputText] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [composerResult, setComposerResult] = useState<any>(null);
  const [composerError, setComposerError] = useState<any>(null);

  // Clarification / Resume State
  const [clarificationAnswer, setClarificationAnswer] = useState("");
  const [isResuming, setIsResuming] = useState(false);

  // Automations List State
  const [automations, setAutomations] = useState<AutomationItem[]>([]);
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [isLoadingAutomations, setIsLoadingAutomations] = useState(false);

  // Audit Logs State
  const [auditLogs, setAuditLogs] = useState<AuditLogItem[]>([]);
  const [selectedAuditAutoId, setSelectedAuditAutoId] = useState<string | null>(null);
  const [isLoadingAudit, setIsLoadingAudit] = useState(false);
  const [autoRefreshAudit, setAutoRefreshAudit] = useState(false);

  // Host Agent State
  const [hostAgents, setHostAgents] = useState<HostAgentItem[]>([]);
  const [generatedTokenInfo, setGeneratedTokenInfo] = useState<{ token: string; command: string } | null>(null);
  const [isGeneratingToken, setIsGeneratingToken] = useState(false);
  const [isLoadingAgents, setIsLoadingAgents] = useState(false);

  // Client Mount & Timezone for Hydration Safety
  const [mounted, setMounted] = useState(false);
  const [userTimezone, setUserTimezone] = useState("UTC");

  useEffect(() => {
    setMounted(true);
    try {
      const tz = Intl.DateTimeFormat().resolvedOptions().timeZone;
      if (tz) setUserTimezone(tz);
    } catch {}
  }, []);

  // Check Health
  const checkHealth = useCallback(async () => {
    try {
      const res = await fetch(`${apiUrl}/health`);
      if (res.ok) {
        setIsGatewayHealthy(true);
      } else {
        setIsGatewayHealthy(false);
      }
    } catch {
      setIsGatewayHealthy(false);
    }
  }, [apiUrl]);

  // Load Automations
  const fetchAutomations = useCallback(async () => {
    setIsLoadingAutomations(true);
    try {
      const url = statusFilter === "all"
        ? `${apiUrl}/api/v1/automations`
        : `${apiUrl}/api/v1/automations?status=${statusFilter}`;
      const res = await fetch(url);
      if (res.ok) {
        const data = await res.json();
        setAutomations(data.automations || []);
      }
    } catch (e) {
      console.error("Failed to fetch automations", e);
    } finally {
      setIsLoadingAutomations(false);
    }
  }, [apiUrl, statusFilter]);

  // Load Audit Logs
  const fetchAuditLogs = useCallback(async () => {
    setIsLoadingAudit(true);
    try {
      const url = selectedAuditAutoId
        ? `${apiUrl}/api/v1/automations/${selectedAuditAutoId}/audit`
        : `${apiUrl}/api/v1/audit`;
      const res = await fetch(url);
      if (res.ok) {
        const data = await res.json();
        setAuditLogs(data.audit_logs || []);
      }
    } catch (e) {
      console.error("Failed to fetch audit logs", e);
    } finally {
      setIsLoadingAudit(false);
    }
  }, [apiUrl, selectedAuditAutoId]);

  // Load Host Agents
  const fetchHostAgents = useCallback(async () => {
    setIsLoadingAgents(true);
    try {
      const res = await fetch(`${apiUrl}/api/v1/host-agents`);
      if (res.ok) {
        const data = await res.json();
        setHostAgents(data.host_agents || []);
      }
    } catch (e) {
      console.error("Failed to fetch host agents", e);
    } finally {
      setIsLoadingAgents(false);
    }
  }, [apiUrl]);

  // Generate Token
  const generateHostAgentToken = async () => {
    setIsGeneratingToken(true);
    try {
      const res = await fetch(`${apiUrl}/api/v1/host-agents/tokens`, { method: "POST" });
      if (res.ok) {
        const data = await res.json();
        setGeneratedTokenInfo(data);
        fetchHostAgents();
      }
    } catch (e) {
      console.error("Failed to generate token", e);
    } finally {
      setIsGeneratingToken(false);
    }
  };

  useEffect(() => {
    checkHealth();
  }, [checkHealth]);

  useEffect(() => {
    if (activeTab === "automations") {
      fetchAutomations();
    } else if (activeTab === "audit") {
      fetchAuditLogs();
    } else if (activeTab === "host-agent") {
      fetchHostAgents();
    }
  }, [activeTab, fetchAutomations, fetchAuditLogs, fetchHostAgents]);

  useEffect(() => {
    let timer: any;
    if (autoRefreshAudit && activeTab === "audit") {
      timer = setInterval(() => {
        fetchAuditLogs();
      }, 3000);
    } else if (activeTab === "host-agent") {
      timer = setInterval(() => {
        fetchHostAgents();
      }, 5000);
    }
    return () => clearInterval(timer);
  }, [autoRefreshAudit, activeTab, fetchAuditLogs, fetchHostAgents]);

  // Handle Create Automation
  const handleCreateAutomation = async (textToSubmit?: string) => {
    const text = textToSubmit || inputText;
    if (!text.trim()) return;

    setIsSubmitting(true);
    setComposerResult(null);
    setComposerError(null);
    setClarificationAnswer("");

    try {
      const timezone = userTimezone || "UTC";
      const res = await fetch(`${apiUrl}/api/v1/automations`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, timezone })
      });

      const data = await res.json();
      if (!res.ok) {
        setComposerError(data.detail || data);
      } else if (data.confirmation_required) {
        // Multi-stage destructive action confirmation
        const isWin = typeof navigator !== "undefined" && navigator.platform.toLowerCase().includes("win");
        const confRes = await confirmDestructiveAction(
          data.preview || {},
          data.risk_tier || "medium",
          isWin
        );

        if (confRes.confirmed) {
          const resumeRes = await fetch(`${apiUrl}/api/v1/automations/${data.id}/resume`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              user_response: {
                confirmed: true,
                steps: confRes.steps,
                path: confRes.path
              }
            })
          });
          const resumeData = await resumeRes.json();
          setComposerResult(resumeData);
          fetchAutomations();
        } else {
          setComposerResult({
            ...data,
            status: "cancelled",
            cancellation_message: "Destructive action confirmation was cancelled. Nothing was executed or deleted."
          });
        }
      } else {
        setComposerResult(data);
      }
    } catch (err: any) {
      setComposerError({ error: "NETWORK_ERROR", message: err.message || "Failed to reach API Gateway" });
    } finally {
      setIsSubmitting(false);
    }
  };

  // Handle Ambiguity Resume
  const handleResumeAutomation = async () => {
    if (!composerResult?.id || !clarificationAnswer.trim()) return;
    setIsResuming(true);
    try {
      const res = await fetch(`${apiUrl}/api/v1/automations/${composerResult.id}/resume`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_response: clarificationAnswer.trim() })
      });
      const data = await res.json();
      if (res.ok) {
        setComposerResult((prev: any) => ({
          ...prev,
          ...data,
          status: data.status || "active",
          clarification_prompt: undefined
        }));
      } else {
        alert(data.detail || "Failed to resume automation");
      }
    } catch (e: any) {
      alert(`Error resuming: ${e.message}`);
    } finally {
      setIsResuming(false);
    }
  };

  // Handle Archive Automation
  const handleArchive = async (id: string) => {
    if (!confirm("Are you sure you want to archive this automation?")) return;
    try {
      const res = await fetch(`${apiUrl}/api/v1/automations/${id}`, {
        method: "DELETE"
      });
      if (res.ok) {
        fetchAutomations();
      }
    } catch (e) {
      console.error("Archive error", e);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
      {/* Top Header */}
      <header className="border-b border-slate-800 bg-slate-900/60 backdrop-blur sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="p-2 bg-indigo-600/20 border border-indigo-500/30 rounded-lg text-indigo-400">
              <Zap className="w-5 h-5" />
            </div>
            <div>
              <h1 className="text-lg font-bold text-white flex items-center gap-2">
                NL-Automation Platform
                <span className="text-xs px-2 py-0.5 rounded-full bg-indigo-950 text-indigo-400 border border-indigo-800">
                  v1.0 Free-Tier
                </span>
              </h1>
              <p className="text-xs text-slate-400">Natural Language Automation Compiler & Execution Engine</p>
            </div>
          </div>

          <div className="flex items-center space-x-4">
            {/* Health Badge */}
            <div className="flex items-center space-x-2 text-xs bg-slate-800/80 px-3 py-1.5 rounded-md border border-slate-700">
              <Server className="w-3.5 h-3.5 text-slate-400" />
              <span>Gateway:</span>
              {isGatewayHealthy === null ? (
                <span className="text-slate-400">Checking...</span>
              ) : isGatewayHealthy ? (
                <span className="text-emerald-400 flex items-center gap-1">
                  <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                  Online (:8080)
                </span>
              ) : (
                <span className="text-rose-400 flex items-center gap-1">
                  <span className="w-2 h-2 rounded-full bg-rose-500" />
                  Unreachable
                </span>
              )}
            </div>

            {/* Navigation Tabs */}
            <div className="flex bg-slate-800/90 p-1 rounded-lg border border-slate-700">
              <button
                onClick={() => setActiveTab("compose")}
                className={`px-3 py-1 text-xs font-medium rounded-md transition-colors flex items-center gap-1.5 ${
                  activeTab === "compose"
                    ? "bg-indigo-600 text-white shadow-sm"
                    : "text-slate-400 hover:text-slate-200"
                }`}
              >
                <Terminal className="w-3.5 h-3.5" />
                Composer
              </button>
              <button
                onClick={() => setActiveTab("automations")}
                className={`px-3 py-1 text-xs font-medium rounded-md transition-colors flex items-center gap-1.5 ${
                  activeTab === "automations"
                    ? "bg-indigo-600 text-white shadow-sm"
                    : "text-slate-400 hover:text-slate-200"
                }`}
              >
                <Layers className="w-3.5 h-3.5" />
                Automations
              </button>
              <button
                onClick={() => setActiveTab("audit")}
                className={`px-3 py-1 text-xs font-medium rounded-md transition-colors flex items-center gap-1.5 ${
                  activeTab === "audit"
                    ? "bg-indigo-600 text-white shadow-sm"
                    : "text-slate-400 hover:text-slate-200"
                }`}
              >
                <Activity className="w-3.5 h-3.5" />
                Audit Trail
              </button>
              <button
                onClick={() => setActiveTab("host-agent")}
                className={`px-3 py-1 text-xs font-medium rounded-md transition-colors flex items-center gap-1.5 ${
                  activeTab === "host-agent"
                    ? "bg-indigo-600 text-white shadow-sm"
                    : "text-slate-400 hover:text-slate-200"
                }`}
              >
                <Laptop className="w-3.5 h-3.5" />
                Host Agent
              </button>
              <a
                href={`${apiUrl}/tracenest`}
                target="_blank"
                rel="noopener noreferrer"
                className="px-3 py-1 text-xs font-medium rounded-md transition-colors flex items-center gap-1.5 text-amber-400 hover:text-amber-300 bg-amber-950/40 hover:bg-amber-900/50 border border-amber-800/50 shadow-sm"
                title="Open TraceNest Observability Dashboard"
              >
                <Layers className="w-3.5 h-3.5" />
                TraceNest Logs
                <ExternalLink className="w-3 h-3 ml-0.5 opacity-70" />
              </a>
            </div>
          </div>
        </div>
      </header>

      {/* Main Body */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-4 md:p-6">
        {/* ================= COMPOSER TAB ================= */}
        {activeTab === "compose" && (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            {/* Left Column: Natural Language Input & Presets */}
            <div className="lg:col-span-6 space-y-6">
              <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-sm">
                <div className="flex items-center justify-between mb-3">
                  <label className="text-sm font-semibold text-slate-200 flex items-center gap-2">
                    <Terminal className="w-4 h-4 text-indigo-400" />
                    Natural Language Input
                  </label>
                  <span className="text-xs text-slate-400" suppressHydrationWarning>
                    Timezone: <code className="text-indigo-300" suppressHydrationWarning>{mounted ? userTimezone : "UTC"}</code>
                  </span>
                </div>

                <div className="relative">
                  <textarea
                    rows={4}
                    value={inputText}
                    onChange={(e) => setInputText(e.target.value)}
                    placeholder="e.g. Clean my recycle bin when it reaches 80%..."
                    className="w-full bg-slate-950 border border-slate-700/80 rounded-lg p-3 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent font-mono"
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
                        handleCreateAutomation();
                      }
                    }}
                  />
                  <div className="flex items-center justify-between mt-3">
                    <span className="text-xs text-slate-500">
                      Press <kbd className="px-1.5 py-0.5 bg-slate-800 rounded border border-slate-700 text-slate-400">Ctrl+Enter</kbd> to compile
                    </span>
                    <button
                      onClick={() => handleCreateAutomation()}
                      disabled={isSubmitting || !inputText.trim()}
                      className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed text-white text-xs font-semibold rounded-lg shadow flex items-center gap-2 transition-all"
                    >
                      {isSubmitting ? (
                        <>
                          <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                          Analyzing Pipeline...
                        </>
                      ) : (
                        <>
                          <Send className="w-3.5 h-3.5" />
                          Compile & Register
                        </>
                      )}
                    </button>
                  </div>
                </div>
              </div>

              {/* Preset Prompts Section */}
              <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-sm">
                <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">
                  Specification Test Scenarios
                </h3>
                <div className="space-y-2.5">
                  {PRESET_PROMPTS.map((preset, idx) => (
                    <button
                      key={idx}
                      onClick={() => {
                        setInputText(preset.prompt);
                        handleCreateAutomation(preset.prompt);
                      }}
                      className="w-full text-left p-3 rounded-lg bg-slate-950/60 border border-slate-800/80 hover:border-indigo-500/50 hover:bg-slate-800/40 transition-all group flex items-start justify-between"
                    >
                      <div className="space-y-1">
                        <div className="text-xs font-medium text-slate-200 group-hover:text-indigo-300">
                          {preset.label}
                        </div>
                        <div className="text-xs text-slate-400 font-mono">
                          "{preset.prompt}"
                        </div>
                      </div>
                      <ChevronRight className="w-4 h-4 text-slate-600 group-hover:text-indigo-400 shrink-0 mt-1 transition-transform group-hover:translate-x-0.5" />
                    </button>
                  ))}
                </div>
              </div>
            </div>

            {/* Right Column: Execution Pipeline Visualization */}
            <div className="lg:col-span-6 space-y-6">
              {/* Idle State Banner */}
              {!composerResult && !composerError && !isSubmitting && (
                <div className="h-full min-h-[350px] border border-dashed border-slate-800 rounded-xl flex flex-col items-center justify-center p-8 text-center bg-slate-900/30">
                  <div className="p-3 bg-slate-800/50 rounded-full text-slate-500 mb-3">
                    <Terminal className="w-6 h-6" />
                  </div>
                  <h4 className="text-sm font-medium text-slate-300 mb-1">Awaiting Automation Intent</h4>
                  <p className="text-xs text-slate-500 max-w-sm">
                    Type a natural language instruction or click a test scenario on the left to watch the multi-stage parsing, safety guardrails, and decision agent pipeline in action.
                  </p>
                </div>
              )}

              {/* Loading Indicator */}
              {isSubmitting && (
                <div className="bg-slate-900 border border-slate-800 rounded-xl p-8 flex flex-col items-center justify-center space-y-4">
                  <RefreshCw className="w-8 h-8 text-indigo-400 animate-spin" />
                  <div className="text-center">
                    <div className="text-sm font-medium text-slate-200">Executing Safety & Reasoning Chain</div>
                    <div className="text-xs text-slate-400 mt-1">
                      Intent Parser → Guardrail Pre-Gate (Llama Guard 4) → LangGraph Decision Agent
                    </div>
                  </div>
                </div>
              )}

              {/* Error / Blocked Alert */}
              {composerError && (
                <div className="bg-rose-950/20 border border-rose-800/60 rounded-xl p-5 shadow-sm space-y-4">
                  <div className="flex items-start space-x-3">
                    <div className="p-2 bg-rose-900/40 text-rose-400 rounded-lg">
                      <ShieldAlert className="w-5 h-5" />
                    </div>
                    <div>
                      <h4 className="text-sm font-semibold text-rose-200">
                        {composerError.error === "GUARDRAIL_BLOCKED"
                          ? "Blocked by Security Guardrail Policy"
                          : composerError.error === "FORBIDDEN_DELETION"
                          ? "Hard Denylist Refusal (Cannot Wipe Drive Root / Core System Folder)"
                          : composerError.error === "content_policy_blocked"
                          ? "Blocked by Content Policy (Hazard Boundary — No Override)"
                          : composerError.error === "compound_automation_rejected"
                          ? "Single-Intent Contract Enforced (422)"
                          : "Automation Pipeline Error"}
                      </h4>
                      <p className="text-xs text-rose-300/80 mt-1">
                        {composerError.reason || composerError.message || JSON.stringify(composerError)}
                      </p>
                    </div>
                  </div>

                  {composerError.categories && (
                    <div className="bg-rose-900/20 border border-rose-800/40 rounded-lg p-3">
                      <div className="text-xs font-semibold text-rose-300 mb-1">Violated Security Categories:</div>
                      <div className="flex flex-wrap gap-1.5">
                        {composerError.categories.map((cat: string, i: number) => (
                          <span key={i} className="px-2 py-0.5 text-[10px] font-mono bg-rose-950 text-rose-300 border border-rose-700/50 rounded">
                            {cat}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {composerError.suggested_alternative && (
                    <div className="text-xs text-slate-300 bg-slate-900/80 border border-slate-700/80 rounded-lg p-3">
                      <span className="font-semibold text-indigo-300">Suggested Safe Alternative: </span>
                      {composerError.suggested_alternative}
                    </div>
                  )}
                </div>
              )}

              {/* Success Result View */}
              {composerResult && (
                <div className="space-y-4">
                  {/* Status Banner */}
                  <div className={`p-4 rounded-xl border flex items-center justify-between ${
                    composerResult.status === "active"
                      ? "bg-emerald-950/20 border-emerald-800/60 text-emerald-200"
                      : "bg-amber-950/20 border-amber-800/60 text-amber-200"
                  }`}>
                    <div className="flex items-center space-x-3">
                      {composerResult.status === "active" ? (
                        <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                      ) : (
                        <AlertTriangle className="w-5 h-5 text-amber-400" />
                      )}
                      <div>
                        <div className="text-xs font-semibold uppercase tracking-wider">
                          Status: {composerResult.status.toUpperCase()}
                        </div>
                        <div className="text-xs opacity-90">
                          {composerResult.status === "active"
                            ? "Automation registered & active in trigger runtime"
                            : "Paused at LangGraph checkpoint: Clarification required"}
                        </div>
                      </div>
                    </div>
                    <span className="text-[10px] font-mono bg-slate-900/80 px-2 py-1 rounded border border-slate-700 text-slate-300">
                      ID: {composerResult.id ? composerResult.id.slice(0, 8) : "N/A"}
                    </span>
                  </div>

                  {/* Ambiguity Clarification Modal/Card */}
                  {composerResult.clarification_prompt && (
                    <div className="bg-amber-950/30 border border-amber-700/60 rounded-xl p-5 space-y-3">
                      <div className="flex items-start gap-2.5">
                        <HelpCircle className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
                        <div>
                          <div className="text-xs font-semibold text-amber-300">Agent Clarification Required</div>
                          <p className="text-sm text-amber-100 font-medium mt-1">
                            {composerResult.clarification_prompt}
                          </p>
                        </div>
                      </div>

                      <div className="pt-2 flex gap-2">
                        <input
                          type="text"
                          value={clarificationAnswer}
                          onChange={(e) => setClarificationAnswer(e.target.value)}
                          placeholder="e.g. clean it when it is 80% full"
                          className="flex-1 bg-slate-950 border border-amber-600/50 rounded-lg px-3 py-2 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-amber-400"
                          onKeyDown={(e) => {
                            if (e.key === "Enter") handleResumeAutomation();
                          }}
                        />
                        <button
                          onClick={handleResumeAutomation}
                          disabled={isResuming || !clarificationAnswer.trim()}
                          className="px-3 py-2 bg-amber-600 hover:bg-amber-500 disabled:opacity-50 text-slate-950 text-xs font-semibold rounded-lg shadow transition-all"
                        >
                          {isResuming ? "Resuming..." : "Submit Answer"}
                        </button>
                      </div>
                    </div>
                  )}

                  {/* Structured Plan Details Card */}
                  <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-sm space-y-4">
                    <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                      <h4 className="text-xs font-semibold text-slate-300 uppercase tracking-wider flex items-center gap-2">
                        <Layers className="w-4 h-4 text-indigo-400" />
                        Verified Automation Plan
                      </h4>
                      <div className="flex items-center gap-1.5 text-xs text-emerald-400 bg-emerald-950/40 px-2 py-0.5 rounded border border-emerald-800">
                        <ShieldCheck className="w-3.5 h-3.5" />
                        Guardrail Approved
                      </div>
                    </div>

                    <div className="grid grid-cols-2 gap-3 text-xs">
                      <div className="bg-slate-950 p-3 rounded-lg border border-slate-800/80">
                        <span className="text-slate-500 block mb-1">Trigger Mechanism</span>
                        <div className="font-semibold text-indigo-300">
                          {composerResult.plan?.trigger?.type || "unknown"}
                        </div>
                        <div className="text-[11px] text-slate-400 mt-1 font-mono">
                          {JSON.stringify(composerResult.plan?.trigger?.params || {})}
                        </div>
                      </div>

                      <div className="bg-slate-950 p-3 rounded-lg border border-slate-800/80">
                        <span className="text-slate-500 block mb-1">Target Action</span>
                        <div className="font-semibold text-emerald-300">
                          {composerResult.plan?.action?.name || "unknown"}
                        </div>
                        <div className="text-[11px] text-slate-400 mt-1 font-mono">
                          {JSON.stringify(composerResult.plan?.action?.params || {})}
                        </div>
                      </div>
                    </div>

                    {/* Quick Link to Tab */}
                    <div className="flex justify-end pt-2">
                      <button
                        onClick={() => {
                          setActiveTab("automations");
                          fetchAutomations();
                        }}
                        className="text-xs text-indigo-400 hover:text-indigo-300 flex items-center gap-1"
                      >
                        View in Automations List
                        <ChevronRight className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* ================= AUTOMATIONS TAB ================= */}
        {activeTab === "automations" && (
          <div className="space-y-6">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div>
                <h2 className="text-base font-bold text-white">Registered Automations</h2>
                <p className="text-xs text-slate-400">View and manage scheduled jobs and active threshold watchers</p>
              </div>

              <div className="flex items-center gap-3">
                <div className="flex bg-slate-900 border border-slate-800 rounded-lg p-1 text-xs">
                  {["all", "active", "draft", "archived"].map((status) => (
                    <button
                      key={status}
                      onClick={() => setStatusFilter(status)}
                      className={`px-2.5 py-1 rounded capitalize transition-colors ${
                        statusFilter === status
                          ? "bg-slate-800 text-white font-semibold"
                          : "text-slate-400 hover:text-slate-200"
                      }`}
                    >
                      {status}
                    </button>
                  ))}
                </div>
                <button
                  onClick={fetchAutomations}
                  disabled={isLoadingAutomations}
                  className="p-2 bg-slate-900 hover:bg-slate-800 border border-slate-800 rounded-lg text-slate-300 hover:text-white transition-colors"
                >
                  <RefreshCw className={`w-4 h-4 ${isLoadingAutomations ? "animate-spin" : ""}`} />
                </button>
              </div>
            </div>

            {/* List */}
            {isLoadingAutomations ? (
              <div className="p-12 text-center text-slate-500 flex flex-col items-center justify-center space-y-2">
                <RefreshCw className="w-6 h-6 animate-spin text-indigo-400" />
                <span className="text-xs">Loading automations from Postgres...</span>
              </div>
            ) : automations.length === 0 ? (
              <div className="border border-dashed border-slate-800 rounded-xl p-12 text-center bg-slate-900/30">
                <Layers className="w-8 h-8 text-slate-600 mx-auto mb-2" />
                <div className="text-sm font-medium text-slate-400">No automations found</div>
                <p className="text-xs text-slate-500 mt-1">Compile your first automation using the Composer tab</p>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {automations.map((item) => (
                  <div
                    key={item.id}
                    className="bg-slate-900 border border-slate-800 rounded-xl p-5 flex flex-col justify-between hover:border-slate-700 transition-all shadow-sm"
                  >
                    <div className="space-y-3">
                      <div className="flex items-center justify-between">
                        <span
                          className={`text-[10px] font-semibold uppercase px-2 py-0.5 rounded-full border ${
                            item.status === "active"
                              ? "bg-emerald-950/60 text-emerald-400 border-emerald-800/80"
                              : item.status === "draft"
                              ? "bg-amber-950/60 text-amber-400 border-amber-800/80"
                              : "bg-slate-800 text-slate-400 border-slate-700"
                          }`}
                        >
                          {item.status}
                        </span>
                        <span className="text-[10px] font-mono text-slate-500" suppressHydrationWarning>
                          {mounted ? new Date(item.created_at).toLocaleDateString() : ""}
                        </span>
                      </div>

                      <div>
                        <div className="text-xs font-semibold text-slate-200 line-clamp-2">
                          "{item.raw_text}"
                        </div>
                      </div>

                      <div className="bg-slate-950 p-2.5 rounded-lg border border-slate-800/80 space-y-1.5 text-[11px]">
                        <div className="flex items-center justify-between">
                          <span className="text-slate-500">Trigger:</span>
                          <span className="font-mono text-indigo-300">
                            {item.structured_plan?.trigger?.type || "N/A"}
                          </span>
                        </div>
                        <div className="flex items-center justify-between">
                          <span className="text-slate-500">Action:</span>
                          <span className="font-mono text-emerald-300">
                            {item.structured_plan?.action?.name || "N/A"}
                          </span>
                        </div>
                      </div>
                    </div>

                    <div className="border-t border-slate-800 pt-3 mt-4 flex items-center justify-between">
                      <button
                        onClick={() => {
                          setSelectedAuditAutoId(item.id);
                          setActiveTab("audit");
                        }}
                        className="text-xs text-indigo-400 hover:text-indigo-300 flex items-center gap-1"
                      >
                        <Activity className="w-3.5 h-3.5" />
                        Audit Trail
                      </button>

                      {item.status !== "archived" && (
                        <button
                          onClick={() => handleArchive(item.id)}
                          className="text-xs text-rose-400 hover:text-rose-300 flex items-center gap-1 p-1 hover:bg-rose-950/40 rounded transition-colors"
                          title="Archive Automation"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                          Archive
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* ================= AUDIT TRAIL TAB ================= */}
        {activeTab === "audit" && (
          <div className="space-y-6">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div>
                <div className="flex items-center gap-2">
                  <h2 className="text-base font-bold text-white">Security & Execution Audit Trail</h2>
                  {selectedAuditAutoId && (
                    <span className="text-xs bg-indigo-950 text-indigo-400 border border-indigo-800 px-2 py-0.5 rounded flex items-center gap-1">
                      Filtering: {selectedAuditAutoId.slice(0, 8)}...
                      <button
                        onClick={() => setSelectedAuditAutoId(null)}
                        className="hover:text-white font-bold ml-1"
                      >
                        ×
                      </button>
                    </span>
                  )}
                </div>
                <p className="text-xs text-slate-400">PostgreSQL immutable audit trail recording all security checks and triggers</p>
              </div>

              <div className="flex items-center gap-3">
                <label className="text-xs text-slate-400 flex items-center gap-1.5 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={autoRefreshAudit}
                    onChange={(e) => setAutoRefreshAudit(e.target.checked)}
                    className="rounded bg-slate-900 border-slate-700 text-indigo-600 focus:ring-0"
                  />
                  Live Poll (3s)
                </label>
                <button
                  onClick={fetchAuditLogs}
                  disabled={isLoadingAudit}
                  className="p-2 bg-slate-900 hover:bg-slate-800 border border-slate-800 rounded-lg text-slate-300 hover:text-white transition-colors"
                >
                  <RefreshCw className={`w-4 h-4 ${isLoadingAudit ? "animate-spin" : ""}`} />
                </button>
              </div>
            </div>

            {/* Audit Log Table / Stream */}
            {isLoadingAudit && auditLogs.length === 0 ? (
              <div className="p-12 text-center text-slate-500 flex flex-col items-center justify-center space-y-2">
                <RefreshCw className="w-6 h-6 animate-spin text-indigo-400" />
                <span className="text-xs">Fetching audit events...</span>
              </div>
            ) : auditLogs.length === 0 ? (
              <div className="border border-dashed border-slate-800 rounded-xl p-12 text-center bg-slate-900/30">
                <Activity className="w-8 h-8 text-slate-600 mx-auto mb-2" />
                <div className="text-sm font-medium text-slate-400">No audit events logged yet</div>
              </div>
            ) : (
              <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-sm">
                <div className="divide-y divide-slate-800">
                  {auditLogs.map((log) => {
                    const isBlocked = log.event_type.includes("blocked") || log.event_type.includes("failed");
                    const isApproved = log.event_type.includes("approved") || log.event_type.includes("registered") || log.event_type.includes("executed");
                    return (
                      <div key={log.id} className="p-4 hover:bg-slate-800/30 transition-colors flex flex-col sm:flex-row sm:items-start justify-between gap-3 text-xs">
                        <div className="space-y-1">
                          <div className="flex items-center gap-2">
                            <span
                              className={`px-2 py-0.5 rounded text-[10px] font-semibold uppercase font-mono border ${
                                isBlocked
                                  ? "bg-rose-950/60 text-rose-300 border-rose-800"
                                  : isApproved
                                  ? "bg-emerald-950/60 text-emerald-300 border-emerald-800"
                                  : "bg-slate-800 text-slate-300 border-slate-700"
                              }`}
                            >
                              {log.event_type}
                            </span>
                            {log.automation_id && (
                              <button
                                onClick={() => setSelectedAuditAutoId(log.automation_id)}
                                className="text-[11px] font-mono text-indigo-400 hover:underline"
                              >
                                {log.automation_id.slice(0, 8)}
                              </button>
                            )}
                          </div>
                          <div className="text-[11px] font-mono text-slate-300 bg-slate-950 p-2 rounded border border-slate-800/80 max-w-2xl overflow-x-auto">
                            {JSON.stringify(log.payload)}
                          </div>
                        </div>

                        <div className="text-[10px] text-slate-500 font-mono shrink-0" suppressHydrationWarning>
                          {mounted ? `${new Date(log.timestamp).toLocaleTimeString()} · ${new Date(log.timestamp).toLocaleDateString()}` : ""}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        )}

        {/* ================= HOST AGENT TAB ================= */}
        {activeTab === "host-agent" && (
          <div className="space-y-6">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div>
                <h2 className="text-base font-bold text-white flex items-center gap-2">
                  <Laptop className="w-5 h-5 text-indigo-400" />
                  Cross-Platform Host Agent
                </h2>
                <p className="text-xs text-slate-400">
                  Runs natively on Windows, Linux, or macOS to monitor local storage and execute host-boundary automations without granting root to Docker.
                </p>
              </div>

              <div className="flex items-center gap-3">
                <button
                  onClick={generateHostAgentToken}
                  disabled={isGeneratingToken}
                  className="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-xs font-semibold rounded-lg shadow flex items-center gap-2 transition-all"
                >
                  <RefreshCw className={`w-3.5 h-3.5 ${isGeneratingToken ? "animate-spin" : ""}`} />
                  Generate Agent Token
                </button>
                <button
                  onClick={fetchHostAgents}
                  disabled={isLoadingAgents}
                  className="p-2 bg-slate-900 hover:bg-slate-800 border border-slate-800 rounded-lg text-slate-300 hover:text-white transition-colors"
                >
                  <RefreshCw className={`w-4 h-4 ${isLoadingAgents ? "animate-spin" : ""}`} />
                </button>
              </div>
            </div>

            {/* Token Generation Banner */}
            {generatedTokenInfo && (
              <div className="bg-indigo-950/40 border border-indigo-700/60 rounded-xl p-5 space-y-3">
                <div className="flex items-start justify-between">
                  <div>
                    <h3 className="text-xs font-semibold text-indigo-300 uppercase tracking-wider">
                      New Host Agent Registration Token
                    </h3>
                    <p className="text-xs text-slate-300 mt-1">
                      Run this command in a terminal on your host machine to start the agent:
                    </p>
                  </div>
                  <span className="text-[10px] font-mono bg-indigo-900/60 px-2 py-0.5 rounded text-indigo-300 border border-indigo-700">
                    One-Time Token
                  </span>
                </div>

                <div className="bg-slate-950 p-3 rounded-lg border border-indigo-900/80 font-mono text-xs text-emerald-400 select-all overflow-x-auto">
                  {generatedTokenInfo.command}
                </div>
              </div>
            )}

            {/* Connected Host Agents */}
            <div className="space-y-4">
              <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                Registered Host Agents ({hostAgents.length})
              </h3>

              {isLoadingAgents && hostAgents.length === 0 ? (
                <div className="p-12 text-center text-slate-500 flex flex-col items-center justify-center space-y-2">
                  <RefreshCw className="w-6 h-6 animate-spin text-indigo-400" />
                  <span className="text-xs">Fetching registered agents...</span>
                </div>
              ) : hostAgents.length === 0 ? (
                <div className="border border-dashed border-slate-800 rounded-xl p-12 text-center bg-slate-900/30">
                  <Laptop className="w-8 h-8 text-slate-600 mx-auto mb-2" />
                  <div className="text-sm font-medium text-slate-400">No host agents connected yet</div>
                  <p className="text-xs text-slate-500 mt-1">
                    Click "Generate Agent Token" above and run the command on your host machine to connect.
                  </p>
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {hostAgents.map((agent) => (
                    <div
                      key={agent.id}
                      className="bg-slate-900 border border-slate-800 rounded-xl p-5 flex flex-col justify-between hover:border-slate-700 transition-all shadow-sm"
                    >
                      <div className="space-y-3">
                        <div className="flex items-center justify-between">
                          <span
                            className={`text-[10px] font-semibold uppercase px-2 py-0.5 rounded-full border ${
                              agent.status === "online"
                                ? "bg-emerald-950/60 text-emerald-400 border-emerald-800/80 flex items-center gap-1.5"
                                : "bg-slate-800 text-slate-400 border-slate-700"
                            }`}
                          >
                            {agent.status === "online" && (
                              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                            )}
                            {agent.status}
                          </span>
                          <span className="text-[10px] font-mono text-slate-500" suppressHydrationWarning>
                            {agent.last_seen_at && mounted ? `Seen ${new Date(agent.last_seen_at).toLocaleTimeString()}` : "Offline"}
                          </span>
                        </div>

                        <div>
                          <div className="text-sm font-bold text-white flex items-center gap-2">
                            {agent.distro_name || agent.os_family}
                          </div>
                          <div className="text-xs text-slate-400 font-mono mt-0.5">
                            ID: {agent.id.slice(0, 8)}...
                          </div>
                        </div>

                        <div className="bg-slate-950 p-2.5 rounded-lg border border-slate-800/80 space-y-1.5 text-[11px] font-mono">
                          <div className="flex items-center justify-between">
                            <span className="text-slate-500">OS Family:</span>
                            <span className="text-indigo-300">{agent.os_family}</span>
                          </div>
                          {agent.package_manager && (
                            <div className="flex items-center justify-between">
                              <span className="text-slate-500">Package Mgr:</span>
                              <span className="text-slate-300">{agent.package_manager}</span>
                            </div>
                          )}
                          {agent.trash_path && (
                            <div className="flex items-center justify-between">
                              <span className="text-slate-500">Trash Path:</span>
                              <span className="text-slate-400 truncate max-w-[150px]">{agent.trash_path}</span>
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

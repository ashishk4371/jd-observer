// Sidepanel Script for Job Description Analyzer

// Configure PDF.js worker
if (window.pdfjsLib) {
  window.pdfjsLib.GlobalWorkerOptions.workerSrc = chrome.runtime.getURL('lib/pdf.worker.min.js');
}

// State
let state = {
  apiBaseUrl: "http://localhost:8000",
  provider: "claude",
  apiKeys: { claude: "", gemini: "", openai: "", groq: "" },
  isApiOnline: false,
  resumeId: null,
  resumeFileName: "",
  resumeText: "",
  resumeProfile: null,
  jdText: "",
  analysisResult: null
};

const PROVIDER_LABELS = {
  claude: "Claude",
  gemini: "Gemini",
  openai: "OpenAI",
  groq: "Groq"
};

// Common Technical Skills for Client-side Fallback Parser
const FALLBACK_TECH_SKILLS = [
  "Python", "JavaScript", "TypeScript", "Java", "C++", "C#", "Go", "Rust", "Ruby", "PHP",
  "React", "Angular", "Vue", "Next.js", "Node.js", "Express", "FastAPI", "Django", "Flask",
  "AWS", "Azure", "GCP", "Docker", "Kubernetes", "CI/CD", "Terraform", "Git", "GitHub",
  "SQL", "PostgreSQL", "MySQL", "MongoDB", "Redis", "Elasticsearch", "PyTorch", "TensorFlow",
  "Scikit-Learn", "Pandas", "NumPy", "NLP", "LLM", "Generative AI", "GraphQL", "REST API",
  "Agile", "Scrum", "Jira", "System Design", "Microservices", "Unit Testing", "TDD"
];

// DOM Elements
const elements = {
  apiStatusBadge: document.getElementById("apiStatusBadge"),
  btnSettings: document.getElementById("btnSettings"),
  settingsPanel: document.getElementById("settingsPanel"),
  btnCloseSettings: document.getElementById("btnCloseSettings"),
  btnSaveSettings: document.getElementById("btnSaveSettings"),
  apiUrlInput: document.getElementById("apiUrlInput"),
  providerSelect: document.getElementById("providerSelect"),
  apiKeyLabel: document.getElementById("apiKeyLabel"),
  apiKeyInput: document.getElementById("apiKeyInput"),

  dropZone: document.getElementById("dropZone"),
  resumeFileInput: document.getElementById("resumeFileInput"),
  resumeBadge: document.getElementById("resumeBadge"),
  resumeInfo: document.getElementById("resumeInfo"),
  resumeFileName: document.getElementById("resumeFileName"),
  resumeCharCount: document.getElementById("resumeCharCount"),
  btnRemoveResume: document.getElementById("btnRemoveResume"),
  resumeTextPreview: document.getElementById("resumeTextPreview"),
  profileSnapshotDetails: document.getElementById("profileSnapshotDetails"),
  profileSummaryText: document.getElementById("profileSummaryText"),
  profileSeniorityText: document.getElementById("profileSeniorityText"),
  profileDomainsChips: document.getElementById("profileDomainsChips"),
  profileSkillsChips: document.getElementById("profileSkillsChips"),

  jdInput: document.getElementById("jdInput"),
  btnGrabSelection: document.getElementById("btnGrabSelection"),
  btnAnalyze: document.getElementById("btnAnalyze"),
  analyzeSpinner: document.getElementById("analyzeSpinner"),

  resultsSection: document.getElementById("resultsSection"),
  scoreLevelBadge: document.getElementById("scoreLevelBadge"),
  gaugeProgress: document.getElementById("gaugeProgress"),
  scorePercent: document.getElementById("scorePercent"),

  metricSkill: document.getElementById("metricSkill"),
  metricSemantic: document.getElementById("metricSemantic"),
  metricKeyword: document.getElementById("metricKeyword"),
  barSkill: document.getElementById("barSkill"),
  barSemantic: document.getElementById("barSemantic"),
  barKeyword: document.getElementById("barKeyword"),

  missingSkillsChips: document.getElementById("missingSkillsChips"),
  matchedSkillsChips: document.getElementById("matchedSkillsChips"),
  rewriteList: document.getElementById("rewriteList"),
  additionsList: document.getElementById("additionsList"),
  analysisSummaryText: document.getElementById("analysisSummaryText"),
  actionTipsList: document.getElementById("actionTipsList"),

  llmEngineBadge: document.getElementById("llmEngineBadge"),
  seniorityFitText: document.getElementById("seniorityFitText"),
  requirementMatrixList: document.getElementById("requirementMatrixList"),
  strategicAdviceText: document.getElementById("strategicAdviceText")
};

// Initialize
document.addEventListener("DOMContentLoaded", async () => {
  setupEventListeners();
  await loadSavedState();
  await checkBackendHealth();
  checkPendingJDSelection();
});

// Event Listeners Setup
function setupEventListeners() {
  // Settings toggle
  elements.btnSettings.addEventListener("click", () => {
    elements.settingsPanel.classList.toggle("hidden");
  });
  elements.btnCloseSettings.addEventListener("click", () => {
    elements.settingsPanel.classList.add("hidden");
  });

  // Switching provider swaps in that provider's own stored key (in-memory,
  // without losing whatever was just typed for the previously-selected provider)
  elements.providerSelect.addEventListener("change", () => {
    state.apiKeys[state.provider] = elements.apiKeyInput.value.trim();
    state.provider = elements.providerSelect.value;
    renderProviderKeyField();
  });

  elements.btnSaveSettings.addEventListener("click", async () => {
    const url = elements.apiUrlInput.value.trim().replace(/\/$/, "");
    state.apiBaseUrl = url;
    state.apiKeys[state.provider] = elements.apiKeyInput.value.trim();
    await chrome.storage.local.set({
      apiBaseUrl: url,
      provider: state.provider,
      apiKeys: state.apiKeys
    });
    elements.settingsPanel.classList.add("hidden");
    await checkBackendHealth();
  });

  // Resume Dropzone & File Input
  elements.dropZone.addEventListener("click", () => elements.resumeFileInput.click());
  elements.resumeFileInput.addEventListener("change", (e) => {
    if (e.target.files && e.target.files[0]) {
      handleFileSelected(e.target.files[0]);
    }
  });

  elements.dropZone.addEventListener("dragover", (e) => {
    e.preventDefault();
    elements.dropZone.classList.add("drag-over");
  });

  elements.dropZone.addEventListener("dragleave", () => {
    elements.dropZone.classList.remove("drag-over");
  });

  elements.dropZone.addEventListener("drop", (e) => {
    e.preventDefault();
    elements.dropZone.classList.remove("drag-over");
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileSelected(e.dataTransfer.files[0]);
    }
  });

  elements.btnRemoveResume.addEventListener("click", clearResumeState);

  // Grab Selection Button
  elements.btnGrabSelection.addEventListener("click", grabSelectionFromTab);

  // Analyze Button
  elements.btnAnalyze.addEventListener("click", runAnalysis);

  // Tabs Navigation
  document.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
      document.querySelectorAll(".tab-content").forEach((c) => c.classList.remove("active"));

      e.target.classList.add("active");
      const targetId = e.target.getAttribute("data-tab");
      document.getElementById(targetId).classList.add("active");
    });
  });

  // Listen for messages from background/content script
  chrome.runtime.onMessage.addListener((message) => {
    if (message.type === "JD_TEXT_SELECTED" && message.text) {
      elements.jdInput.value = message.text;
    }
  });
}

// Show the API key field for whichever provider is currently selected
function renderProviderKeyField() {
  elements.providerSelect.value = state.provider;
  elements.apiKeyLabel.textContent = `API Key for ${PROVIDER_LABELS[state.provider]}:`;
  elements.apiKeyInput.placeholder = `Enter your ${PROVIDER_LABELS[state.provider]} API key`;
  elements.apiKeyInput.value = state.apiKeys[state.provider] || "";
}

// Load persisted state from storage
async function loadSavedState() {
  const saved = await chrome.storage.local.get([
    "apiBaseUrl",
    "apiKey",
    "provider",
    "apiKeys",
    "resumeId",
    "resumeFileName",
    "resumeText",
    "resumeProfile",
    "jdInputText"
  ]);

  if (saved.apiBaseUrl) {
    state.apiBaseUrl = saved.apiBaseUrl;
    elements.apiUrlInput.value = saved.apiBaseUrl;
  }

  if (saved.apiKeys) {
    state.apiKeys = { ...state.apiKeys, ...saved.apiKeys };
  } else if (saved.apiKey) {
    // Migrate the old single-key field (previously unused/decorative) under Claude
    state.apiKeys.claude = saved.apiKey;
  }
  if (saved.provider && PROVIDER_LABELS[saved.provider]) {
    state.provider = saved.provider;
  }
  renderProviderKeyField();

  if (saved.resumeText) {
    state.resumeText = saved.resumeText;
    state.resumeFileName = saved.resumeFileName || "resume.pdf";
    state.resumeId = saved.resumeId || null;
    state.resumeProfile = saved.resumeProfile || null;
    renderResumeAttachedUI();
  }

  if (saved.jdInputText) {
    elements.jdInput.value = saved.jdInputText;
  }

  elements.jdInput.addEventListener("input", () => {
    chrome.storage.local.set({ jdInputText: elements.jdInput.value });
  });
}

// Check backend API connection
async function checkBackendHealth() {
  try {
    const res = await fetch(`${state.apiBaseUrl}/health`, { method: "GET" });
    if (res.ok) {
      const data = await res.json();
      state.isApiOnline = true;
      elements.apiStatusBadge.className = "status-badge status-online";
      elements.apiStatusBadge.querySelector(".status-label").textContent = "⚡ API Connected";
      return;
    }
  } catch (err) {
    // API offline
  }
  state.isApiOnline = false;
  elements.apiStatusBadge.className = "status-badge status-offline";
  elements.apiStatusBadge.querySelector(".status-label").textContent = "🌐 Standalone Mode";
}

// Check for pending text selected on page before sidepanel was opened
async function checkPendingJDSelection() {
  const saved = await chrome.storage.local.get(["pending_jd_text", "pending_jd_timestamp"]);
  if (saved.pending_jd_text && (Date.now() - (saved.pending_jd_timestamp || 0) < 60000)) {
    elements.jdInput.value = saved.pending_jd_text;
    // Clear pending flag
    chrome.storage.local.remove(["pending_jd_text", "pending_jd_timestamp"]);
  }
}

// Handle Resume File Upload & Client Parsing
async function handleFileSelected(file) {
  const fname = file.name;
  const ext = fname.substring(fname.lastIndexOf(".")).toLowerCase();

  if (![".pdf", ".docx", ".txt"].includes(ext)) {
    alert("Unsupported file format! Please select a PDF, DOCX, or TXT file.");
    return;
  }

  elements.dropZone.querySelector(".drop-title").textContent = "Extracting text...";

  try {
    let extractedText = "";

    if (ext === ".pdf") {
      extractedText = await extractPdfText(file);
    } else if (ext === ".docx") {
      extractedText = await extractDocxText(file);
    } else {
      extractedText = await file.text();
    }

    if (!extractedText || !extractedText.trim()) {
      alert("Could not extract clean text from file. Please ensure the document is not password-protected or image-only.");
      renderResumeAttachedUI();
      return;
    }

    state.resumeText = extractedText.trim();
    state.resumeFileName = fname;
    state.resumeId = null;
    state.resumeProfile = null;

    // Try uploading to backend API if connected
    if (state.isApiOnline) {
      try {
        const formData = new FormData();
        formData.append("file", file);
        formData.append("provider", state.provider);
        const currentKey = state.apiKeys[state.provider];
        if (currentKey) formData.append("api_key", currentKey);
        const apiRes = await fetch(`${state.apiBaseUrl}/upload_resume`, {
          method: "POST",
          body: formData
        });
        if (apiRes.ok) {
          const apiData = await apiRes.json();
          state.resumeId = apiData.resume_id;
          state.resumeProfile = apiData.resume_profile || null;
        }
      } catch (err) {
        console.log("Backend resume upload failed, using local extraction:", err);
      }
    }

    // Save in storage
    await chrome.storage.local.set({
      resumeText: state.resumeText,
      resumeFileName: state.resumeFileName,
      resumeId: state.resumeId,
      resumeProfile: state.resumeProfile
    });

    renderResumeAttachedUI();
  } catch (err) {
    alert(`File parsing error: ${err.message}`);
    console.error(err);
  } finally {
    elements.dropZone.querySelector(".drop-title").textContent = "Drop PDF, DOCX, or TXT resume";
  }
}

// Client PDF parser via pdfjsLib
async function extractPdfText(file) {
  if (!window.pdfjsLib) throw new Error("PDF.js library is not loaded.");
  const arrayBuffer = await file.arrayBuffer();
  const pdf = await pdfjsLib.getDocument({ data: arrayBuffer }).promise;
  let fullText = "";

  for (let i = 1; i <= pdf.numPages; i++) {
    const page = await pdf.getPage(i);
    const content = await page.getTextContent();
    const strings = content.items.map((item) => item.str);
    fullText += strings.join(" ") + "\n";
  }
  return fullText;
}

// Client DOCX parser via mammoth
async function extractDocxText(file) {
  if (!window.mammoth) throw new Error("Mammoth DOCX parser library is not loaded.");
  const arrayBuffer = await file.arrayBuffer();
  const result = await mammoth.extractRawText({ arrayBuffer: arrayBuffer });
  return result.value;
}

// Render Attached Resume UI
function renderResumeAttachedUI() {
  if (state.resumeText) {
    elements.dropZone.classList.add("hidden");
    elements.resumeInfo.classList.remove("hidden");
    elements.resumeBadge.className = "pill pill-success";
    elements.resumeBadge.textContent = "Resume Ready";

    elements.resumeFileName.textContent = state.resumeFileName;

    // Extract local skills count
    const skills = extractSkillsClient(state.resumeText);
    elements.resumeCharCount.textContent = `${state.resumeText.length.toLocaleString()} chars • ${skills.length} skills detected`;
    elements.resumeTextPreview.value = state.resumeText;

    renderProfileSnapshot(state.resumeProfile);
  } else {
    elements.dropZone.classList.remove("hidden");
    elements.resumeInfo.classList.add("hidden");
    elements.resumeBadge.className = "pill pill-warning";
    elements.resumeBadge.textContent = "No Resume Attached";
    elements.profileSnapshotDetails.classList.add("hidden");
  }
}

// Render the "What We Understood About You" resume profile snapshot
function renderProfileSnapshot(profile) {
  if (!profile) {
    elements.profileSnapshotDetails.classList.add("hidden");
    return;
  }
  elements.profileSnapshotDetails.classList.remove("hidden");
  elements.profileSummaryText.textContent = profile.summary || "No summary available.";
  elements.profileSeniorityText.textContent = profile.seniority_level || "Unknown";

  const domains = profile.domains || [];
  elements.profileDomainsChips.innerHTML = domains.length
    ? domains.map(d => `<span class="chip chip-matched">${escapeHtml(d)}</span>`).join("")
    : `<span class="tab-desc">No specific domains detected.</span>`;

  const skills = profile.skills || [];
  elements.profileSkillsChips.innerHTML = skills.length
    ? skills.map(s => `<span class="chip chip-matched">${escapeHtml(s)}</span>`).join("")
    : `<span class="tab-desc">No skills detected.</span>`;
}

// Clear Resume
async function clearResumeState() {
  state.resumeText = "";
  state.resumeFileName = "";
  state.resumeId = null;
  state.resumeProfile = null;
  await chrome.storage.local.remove(["resumeText", "resumeFileName", "resumeId", "resumeProfile"]);
  renderResumeAttachedUI();
}

// Grab active tab selection
async function grabSelectionFromTab() {
  chrome.runtime.sendMessage({ type: "GET_ACTIVE_TAB_SELECTION" }, (response) => {
    if (response && response.text && response.text.trim()) {
      elements.jdInput.value = response.text.trim();
      chrome.storage.local.set({ jdInputText: elements.jdInput.value });
    } else {
      alert("No text currently selected on active browser page.");
    }
  });
}

// Run Analysis (API or Standalone Fallback)
async function runAnalysis() {
  if (!state.resumeText) {
    alert("Please upload or attach your resume first!");
    elements.dropZone.scrollIntoView({ behavior: "smooth" });
    return;
  }

  const jdText = elements.jdInput.value.trim();
  if (!jdText) {
    alert("Please paste or grab a job description to analyze!");
    elements.jdInput.focus();
    return;
  }

  state.jdText = jdText;
  elements.btnAnalyze.disabled = true;
  elements.analyzeSpinner.classList.remove("hidden");

  try {
    let result = null;

    if (state.isApiOnline) {
      try {
        const payload = {
          resume_id: state.resumeId,
          resume_text: state.resumeText,
          job_description: jdText,
          api_key: state.apiKeys[state.provider] || null,
          provider: state.provider
        };
        const res = await fetch(`${state.apiBaseUrl}/analyze`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });
        if (res.ok) {
          result = await res.json();
        }
      } catch (err) {
        console.warn("Backend API analyze call failed, switching to standalone analysis:", err);
      }
    }

    // Fallback if API not available or failed
    if (!result) {
      result = computeClientAnalysis(state.resumeText, jdText);
    }

    state.analysisResult = result;
    renderAnalysisResults(result);

  } catch (err) {
    alert(`Analysis error: ${err.message}`);
  } finally {
    elements.btnAnalyze.disabled = false;
    elements.analyzeSpinner.classList.add("hidden");
  }
}

// Client-side Fallback Match Engine
function computeClientAnalysis(resumeText, jdText) {
  const rSkills = new Set(extractSkillsClient(resumeText));
  const jSkills = new Set(extractSkillsClient(jdText));

  const matchedSkills = [...jSkills].filter(s => rSkills.has(s)).sort();
  const missingSkills = [...jSkills].filter(s => !rSkills.has(s)).sort();

  const skillCoverage = jSkills.size > 0 ? (matchedSkills.length / jSkills.size) * 100 : 70;

  // Jaccard word overlap
  const rWords = new Set(resumeText.toLowerCase().match(/\b[a-z]{3,}\b/g) || []);
  const jWords = new Set(jdText.toLowerCase().match(/\b[a-z]{3,}\b/g) || []);

  let kwOverlap = 0;
  if (jWords.size > 0) {
    const common = [...jWords].filter(w => rWords.has(w));
    kwOverlap = (common.length / jWords.size) * 100;
  }

  const semSim = (skillCoverage * 0.6) + (kwOverlap * 0.4);
  const overallScore = Math.min(100, Math.max(0, Math.round((0.5 * skillCoverage) + (0.3 * semSim) + (0.2 * kwOverlap))));

  let scoreLevel = "Needs Tailoring";
  if (overallScore >= 80) scoreLevel = "Excellent";
  else if (overallScore >= 65) scoreLevel = "Good";
  else if (overallScore >= 45) scoreLevel = "Moderate";

  const suggestedAdditions = missingSkills.map(s => `Add '${s}' to your Skills or Experience bullets.`);
  const rewrites = missingSkills.slice(0, 3).map(s => `Leveraged ${s} to optimize feature performance and streamline application workflow.`);

  // Generate suggested resume additions reflecting similar experience to the JD requirements
  const resumeAdditions = missingSkills.slice(0, 4).map(s =>
    `Add a bullet demonstrating hands-on experience with ${s} — reframe a past project to highlight this responsibility and quantify the impact (e.g. 'Improved efficiency by X%').`
  );

  const requirementMatches = buildClientRequirementMatches(resumeText, jdText);

  return {
    match_score: overallScore,
    score_level: scoreLevel,
    breakdown: {
      overall_score: overallScore,
      skill_coverage: Math.round(skillCoverage),
      semantic_similarity: Math.round(semSim),
      keyword_similarity: Math.round(kwOverlap)
    },
    skills: {
      matched_skills: matchedSkills,
      missing_skills: missingSkills,
      skill_match_percentage: Math.round(skillCoverage),
      suggested_additions: suggestedAdditions
    },
    experience: {
      experience_gap: missingSkills.length > 0 ? `Target resume contains ${missingSkills.length} unrepresented technical requirements.` : "Strong skill match found.",
      rewrite_suggestions: rewrites
    },
    llm_analysis: {
      is_llm_powered: false,
      provider_used: "Standalone Engine (offline — start the backend for deep AI analysis)",
      seniority_fit: "Not evaluated in standalone mode — connect the backend for a seniority assessment.",
      strategic_advice: "This is a keyword-based estimate only. Start the FastAPI backend (and add an API key in Settings) for a full requirement-by-requirement AI review.",
      requirement_matches: requirementMatches,
      resume_additions: resumeAdditions
    },
    summary: `Overall Match: ${overallScore}% (${scoreLevel}). Detected ${matchedSkills.length} matching skills and ${missingSkills.length} skill gaps.`,
    actionable_tips: [
      missingSkills.length > 0 ? `Incorporate key missing skills: ${missingSkills.slice(0, 4).join(", ")}` : "Highlight core technical achievements.",
      "Ensure action verbs match the seniority requirements in the job description."
    ]
  };
}

// Client-side heuristic requirement matrix (mirrors the backend's non-LLM fallback shape)
function buildClientRequirementMatches(resumeText, jdText) {
  const rBlob = resumeText.toLowerCase();
  const sentences = jdText.split(".").map(s => s.trim()).filter(s => s.length > 20).slice(0, 8);

  const matches = sentences.map(sentence => {
    const words = sentence.toLowerCase().split(/\s+/).filter(w => w.length > 4);
    const matchCount = words.filter(w => rBlob.includes(w)).length;
    const ratio = words.length ? matchCount / words.length : 0;

    let status, evidence = null, suggestedEdit = null;
    if (ratio >= 0.5) {
      status = "Met";
      evidence = "Overlapping terms found across your resume.";
    } else if (ratio >= 0.2) {
      status = "Partial";
      suggestedEdit = `Reframe a relevant past project to explicitly call out: '${sentence.slice(0, 110)}' — quantify the impact.`;
    } else {
      status = "Missing";
      suggestedEdit = `Add a bullet demonstrating experience with: '${sentence.slice(0, 110)}' — reframe a past project and quantify the impact.`;
    }

    return { requirement: sentence.slice(0, 150), status, evidence, suggested_edit: suggestedEdit };
  });

  return matches.length ? matches : [{
    requirement: "General role fit",
    status: "Partial",
    evidence: null,
    suggested_edit: "Quantify your past achievements (e.g. 'Improved efficiency by X%', 'Led team of Y engineers')."
  }];
}

// Extract skills client-side
function extractSkillsClient(text) {
  const found = new Set();
  FALLBACK_TECH_SKILLS.forEach(skill => {
    const esc = skill.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const regex = new RegExp(`(?<!\\w)${esc}(?!\\w)`, 'i');
    if (regex.test(text)) {
      found.add(skill);
    }
  });
  return [...found];
}

// Render Results in UI
function renderAnalysisResults(res) {
  elements.resultsSection.classList.remove("hidden");
  elements.resultsSection.scrollIntoView({ behavior: "smooth" });

  const score = Math.round(res.match_score || res.breakdown.overall_score || 0);
  elements.scorePercent.textContent = `${score}%`;

  // Animate Gauge progress SVG (radius = 50, circumference = 314.15)
  const offset = 314.15 - (314.15 * score / 100);
  elements.gaugeProgress.style.strokeDashoffset = offset;

  // Gauge color based on score
  if (score >= 75) elements.gaugeProgress.style.stroke = "#10b981"; // Emerald
  else if (score >= 50) elements.gaugeProgress.style.stroke = "#f59e0b"; // Amber
  else elements.gaugeProgress.style.stroke = "#f43f5e"; // Rose

  // Score Level Badge
  const level = res.score_level || "Good";
  elements.scoreLevelBadge.textContent = `${level} Match`;
  elements.scoreLevelBadge.className = `score-level-badge level-${level.toLowerCase().replace(" ", "")}`;

  // Metrics Grid & Bars
  const skillVal = Math.round(res.breakdown.skill_coverage || 0);
  const semVal = Math.round(res.breakdown.semantic_similarity || 0);
  const kwVal = Math.round(res.breakdown.keyword_similarity || 0);

  elements.metricSkill.textContent = `${skillVal}%`;
  elements.metricSemantic.textContent = `${semVal}%`;
  elements.metricKeyword.textContent = `${kwVal}%`;

  elements.barSkill.style.width = `${skillVal}%`;
  elements.barSemantic.style.width = `${semVal}%`;
  elements.barKeyword.style.width = `${kwVal}%`;

  // Render Missing & Matched Skill Chips
  const missing = res.skills.missing_skills || [];
  const matched = res.skills.matched_skills || [];

  if (missing.length === 0) {
    elements.missingSkillsChips.innerHTML = `<p class="tab-desc">🎉 Great job! No major skill gaps detected.</p>`;
  } else {
    elements.missingSkillsChips.innerHTML = missing.map(skill => `
      <span class="chip chip-missing">
        + ${escapeHtml(skill)}
        <button class="btn-copy-chip" data-skill="${escapeHtml(skill)}" title="Copy recommendation">Copy</button>
      </span>
    `).join("");
  }

  if (matched.length === 0) {
    elements.matchedSkillsChips.innerHTML = `<p class="tab-desc">No specific tech skills matched directly.</p>`;
  } else {
    elements.matchedSkillsChips.innerHTML = matched.map(skill => `
      <span class="chip chip-matched">✓ ${escapeHtml(skill)}</span>
    `).join("");
  }

  // Copy chip button listeners
  elements.missingSkillsChips.querySelectorAll(".btn-copy-chip").forEach(btn => {
    btn.addEventListener("click", (e) => {
      const s = e.target.getAttribute("data-skill");
      copyToClipboard(`Proficient in ${s} with hands-on application experience.`, e.target);
    });
  });

  // Render Bullet Point Rewrites
  const rewrites = res.experience.rewrite_suggestions || [];
  if (rewrites.length === 0) {
    elements.rewriteList.innerHTML = `<p class="tab-desc">No specific rewrites required.</p>`;
  } else {
    elements.rewriteList.innerHTML = rewrites.map((text, idx) => `
      <div class="rewrite-card">
        <div class="rewrite-text">• ${escapeHtml(text)}</div>
        <button class="btn-copy-bullet" data-text="${escapeHtml(text)}">Copy Bullet</button>
      </div>
    `).join("");

    elements.rewriteList.querySelectorAll(".btn-copy-bullet").forEach(btn => {
      btn.addEventListener("click", (e) => {
        const text = e.target.getAttribute("data-text");
        copyToClipboard(text, e.target);
      });
    });
  }

  // Render Suggested Resume Additions
  const additions = (res.llm_analysis && res.llm_analysis.resume_additions) || [];
  if (additions.length === 0) {
    elements.additionsList.innerHTML = `<p class="tab-desc">No specific additions suggested. Your experience already reflects the role's requirements.</p>`;
  } else {
    elements.additionsList.innerHTML = additions.map((text, idx) => `
      <div class="rewrite-card">
        <div class="rewrite-text">➕ ${escapeHtml(text)}</div>
        <button class="btn-copy-bullet" data-text="${escapeHtml(text)}">Copy Bullet</button>
      </div>
    `).join("");

    elements.additionsList.querySelectorAll(".btn-copy-bullet").forEach(btn => {
      btn.addEventListener("click", (e) => {
        const text = e.target.getAttribute("data-text");
        copyToClipboard(text, e.target);
      });
    });
  }

  // Summary & Tips
  elements.analysisSummaryText.textContent = res.summary || "";
  const tips = res.actionable_tips || [];
  elements.actionTipsList.innerHTML = tips.map(tip => `<li>${escapeHtml(tip)}</li>`).join("");

  // AI Experience Review tab: engine badge, seniority fit, requirement matrix, strategic advice
  const llmAnalysis = res.llm_analysis || {};
  elements.llmEngineBadge.textContent = llmAnalysis.is_llm_powered
    ? `🤖 ${llmAnalysis.provider_used || "AI Engine"}`
    : `⚙️ ${llmAnalysis.provider_used || "Rule Engine"}`;
  elements.seniorityFitText.textContent = llmAnalysis.seniority_fit || "Not evaluated.";
  elements.strategicAdviceText.textContent = llmAnalysis.strategic_advice || "";

  renderRequirementMatrix(llmAnalysis.requirement_matches || []);
}

// Render the requirement-by-requirement match matrix (Met / Partial / Missing)
function renderRequirementMatrix(matches) {
  if (!matches.length) {
    elements.requirementMatrixList.innerHTML = `<p class="tab-desc">No requirement breakdown available for this analysis.</p>`;
    return;
  }

  const statusMeta = {
    Met: { icon: "✅", cls: "status-badge-met" },
    Partial: { icon: "🟡", cls: "status-badge-partial" },
    Missing: { icon: "❌", cls: "status-badge-missing" }
  };

  elements.requirementMatrixList.innerHTML = matches.map((m, idx) => {
    const meta = statusMeta[m.status] || statusMeta.Partial;
    const detailText = m.status === "Met" ? (m.evidence || "") : (m.suggested_edit || "");
    const detailLabel = m.status === "Met" ? "Evidence" : "Suggested edit";
    const copyBtn = m.suggested_edit
      ? `<button class="btn-copy-bullet" data-text="${escapeHtml(m.suggested_edit)}">Copy Bullet</button>`
      : "";

    return `
      <div class="requirement-card ${meta.cls}">
        <div class="requirement-header">
          <span class="requirement-status-badge ${meta.cls}">${meta.icon} ${escapeHtml(m.status)}</span>
          <span class="requirement-text">${escapeHtml(m.requirement)}</span>
        </div>
        ${detailText ? `<div class="requirement-detail"><strong>${detailLabel}:</strong> ${escapeHtml(detailText)}</div>` : ""}
        ${copyBtn}
      </div>
    `;
  }).join("");

  elements.requirementMatrixList.querySelectorAll(".btn-copy-bullet").forEach(btn => {
    btn.addEventListener("click", (e) => {
      const text = e.target.getAttribute("data-text");
      copyToClipboard(text, e.target);
    });
  });
}

// Copy helper
function copyToClipboard(text, btnElement) {
  navigator.clipboard.writeText(text).then(() => {
    const orig = btnElement.textContent;
    btnElement.textContent = "Copied! ✓";
    setTimeout(() => { btnElement.textContent = orig; }, 1800);
  });
}

function escapeHtml(str) {
  return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

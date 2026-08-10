import os
import re
import json
import logging
from typing import Optional, Dict, Any, List, Tuple
from pydantic import BaseModel, Field

from .extractor import extract_skills, extract_years_of_experience

logger = logging.getLogger(__name__)


class ResumeProfileResult(BaseModel):
    is_llm_powered: bool = False
    summary: str = ""
    seniority_level: str = "Unknown"
    total_years_experience: Optional[float] = None
    skills: List[str] = []
    domains: List[str] = []
    roles: List[Dict[str, Any]] = []
    key_achievements: List[str] = []


class LLMExperienceAnalysisResult(BaseModel):
    is_llm_powered: bool = True
    provider_used: str = "Claude Opus 5"
    career_alignment_score: float = Field(..., description="Alignment score between 0 and 100")
    seniority_fit: str = Field(..., description="Seniority and level fit analysis (e.g. Well-aligned)")
    requirement_matches: List[Dict[str, Any]] = Field(default_factory=list)
    responsibility_overlap: List[str] = Field(default_factory=list)
    experience_gaps: List[str] = Field(default_factory=list)
    tailored_bullet_rewrites: List[str] = Field(default_factory=list)
    resume_additions: List[str] = Field(default_factory=list)
    strategic_advice: str = Field(..., description="Strategic application, cover letter, and interview advice")


CLAUDE_MODEL = "claude-opus-5"


def _init_claude(key: str):
    from langchain_anthropic import ChatAnthropic
    # No `temperature`/`top_p`/`top_k` — those are rejected (400) on Claude Opus 5.
    # Thinking is left at its adaptive default; extraction is deterministic enough not to need it disabled.
    return ChatAnthropic(model=CLAUDE_MODEL, api_key=key, max_tokens=4096)


def _init_gemini(key: str):
    from langchain_google_genai import ChatGoogleGenerativeAI
    return ChatGoogleGenerativeAI(model="gemini-2.5-flash", google_api_key=key, temperature=0.2)


def _init_openai(key: str):
    from langchain_openai import ChatOpenAI
    return ChatOpenAI(model="gpt-4o-mini", api_key=key, temperature=0.2)


def _init_groq(key: str):
    from langchain_groq import ChatGroq
    return ChatGroq(model="llama-3.3-70b-versatile", groq_api_key=key, temperature=0.2)


# provider key -> (init function, human-readable label, server-side env var fallbacks)
PROVIDER_REGISTRY: Dict[str, Tuple[Any, str, List[str]]] = {
    "claude": (_init_claude, "Claude Opus 5", ["ANTHROPIC_API_KEY"]),
    "gemini": (_init_gemini, "Gemini 2.5 Flash", ["GEMINI_API_KEY", "GOOGLE_API_KEY"]),
    "openai": (_init_openai, "OpenAI GPT-4o mini", ["OPENAI_API_KEY"]),
    "groq": (_init_groq, "Groq Llama 3.3", ["GROQ_API_KEY"]),
}


def _key_for_provider(name: str, api_key: Optional[str], requested_provider: str) -> Optional[str]:
    """A caller-supplied api_key only applies to the provider it was submitted for —
    otherwise each provider falls back to its own server-side env var(s)."""
    if api_key and requested_provider == name:
        return api_key
    for env_name in PROVIDER_REGISTRY[name][2]:
        val = os.getenv(env_name)
        if val:
            return val
    return None


def _resolve_llm(api_key: Optional[str], provider: str = "auto") -> Tuple[Optional[Any], str]:
    """Resolve a chat model for the requested provider (claude/gemini/openai/groq), or the
    first provider with an available key when provider is "auto". Falls back to the
    heuristic engine if no provider can be initialized."""
    order = [provider] if provider in PROVIDER_REGISTRY else list(PROVIDER_REGISTRY.keys())

    for name in order:
        key = _key_for_provider(name, api_key, provider)
        if not key:
            continue
        init_fn, label, _ = PROVIDER_REGISTRY[name]
        try:
            return init_fn(key), label
        except Exception as e:
            logger.warning(f"Failed to initialize {label}: {e}")

    return None, "rule_engine"


def _extract_text(content: Any) -> str:
    """Claude Opus 5 responses can arrive as a plain string or a list of content blocks
    (e.g. thinking + text, since adaptive thinking is on by default) — normalize to text."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
            elif isinstance(block, str):
                parts.append(block)
        return "".join(parts)
    return str(content)


def _parse_json_response(raw_text: str) -> dict:
    raw_text = raw_text.strip()
    if raw_text.startswith("```"):
        raw_text = raw_text.split("```")[1]
        if raw_text.startswith("json"):
            raw_text = raw_text[4:].strip()
    return json.loads(raw_text)


# ---------------------------------------------------------------------------
# Resume Profile Extraction (run once per unique resume, cached by content hash)
# ---------------------------------------------------------------------------

RESUME_PROFILE_PROMPT = """
You are an expert technical recruiter. Read this ENTIRE resume and extract a structured profile
capturing the candidate's real career narrative — not just a list of keywords. Understand their
career trajectory, the scope of their work, the domains they operated in, and the outcomes they
delivered.

RESUME:
{resume_text}

Return ONLY a valid JSON object matching this exact schema:
{{
  "summary": "2-3 sentence narrative of who this candidate is professionally",
  "seniority_level": "e.g. Mid-level (4 yrs), Senior, Staff",
  "total_years_experience": 4.5,
  "skills": ["Python", "AWS", "React"],
  "domains": ["e-commerce backend systems", "data pipelines"],
  "roles": [
    {{"title": "Software Engineer", "company": "Acme Corp", "duration": "2022-Present", "bullets": ["Built...", "Led..."]}}
  ],
  "key_achievements": ["Reduced checkout latency by 40% by redesigning the payment service", "Led a 4-person team through a platform migration"]
}}
"""


def build_resume_profile(
    resume_text: str,
    api_key: Optional[str] = None,
    provider: str = "auto"
) -> ResumeProfileResult:
    """Extract a structured, reusable profile from a resume. Called once per unique resume."""
    llm, provider_used = _resolve_llm(api_key, provider)

    if llm:
        try:
            prompt = RESUME_PROFILE_PROMPT.format(resume_text=resume_text[:16000])
            response = llm.invoke(prompt)
            data = _parse_json_response(_extract_text(response.content))
            return ResumeProfileResult(
                is_llm_powered=True,
                summary=data.get("summary", ""),
                seniority_level=data.get("seniority_level", "Unknown"),
                total_years_experience=data.get("total_years_experience"),
                skills=data.get("skills", []),
                domains=data.get("domains", []),
                roles=data.get("roles", []),
                key_achievements=data.get("key_achievements", []),
            )
        except Exception as err:
            logger.error(f"Resume profile LLM extraction failed: {err}")

    return heuristic_resume_profile(resume_text)


SECTION_HEADER_RE = re.compile(
    r"^\s*(experience|work experience|employment history|education|skills|"
    r"technical skills|projects|summary|profile|objective)\s*:?\s*$",
    re.IGNORECASE
)
BULLET_LINE_RE = re.compile(r"^\s*[•\-\*•]\s*|^\s*\d+[.)]\s+")


def heuristic_resume_profile(resume_text: str) -> ResumeProfileResult:
    """Non-LLM fallback: section-split the resume and pull out bullets/skills heuristically."""
    lines = [l.rstrip() for l in resume_text.splitlines()]

    sections: Dict[str, List[str]] = {}
    current = "header"
    sections[current] = []
    for line in lines:
        header_match = SECTION_HEADER_RE.match(line.strip())
        if header_match:
            current = header_match.group(1).lower()
            sections.setdefault(current, [])
            continue
        sections.setdefault(current, []).append(line)

    def bullets_from(section_names: List[str]) -> List[str]:
        out = []
        for name in section_names:
            for line in sections.get(name, []):
                if BULLET_LINE_RE.match(line) and len(line.strip()) > 10:
                    out.append(BULLET_LINE_RE.sub("", line).strip())
        return out

    experience_bullets = bullets_from(["experience", "work experience", "employment history"])
    if not experience_bullets:
        # No recognizable section headers — treat any bullet-like line in the whole doc as experience
        experience_bullets = [
            BULLET_LINE_RE.sub("", l).strip()
            for l in lines if BULLET_LINE_RE.match(l) and len(l.strip()) > 10
        ]

    summary_lines = sections.get("summary") or sections.get("profile") or sections.get("objective")
    if summary_lines:
        summary = " ".join(l.strip() for l in summary_lines if l.strip())[:400]
    else:
        non_empty_header_lines = [l.strip() for l in sections.get("header", []) if l.strip()]
        summary = " ".join(non_empty_header_lines[:3])[:400]

    total_years = extract_years_of_experience(resume_text)
    if total_years is not None:
        seniority_level = f"~{total_years:g} years of experience"
    else:
        seniority_level = "Unknown (years of experience not detected)"

    key_achievements = [b for b in experience_bullets if re.search(r"\d", b)][:6]
    if not key_achievements:
        key_achievements = experience_bullets[:4]

    return ResumeProfileResult(
        is_llm_powered=False,
        summary=summary or "No summary detected — resume parsed via heuristic section splitting.",
        seniority_level=seniority_level,
        total_years_experience=total_years,
        skills=extract_skills(resume_text),
        domains=[],
        roles=[{"title": "Experience", "company": None, "duration": None, "bullets": experience_bullets[:20]}] if experience_bullets else [],
        key_achievements=key_achievements,
    )


# ---------------------------------------------------------------------------
# Requirement-by-requirement matching (resume profile <-> job description)
# ---------------------------------------------------------------------------

MATCH_PROMPT = """
You are an expert Executive Career Coach and ATS Hiring Specialist.
You already have a structured understanding of the candidate's background (given below as JSON),
built from their full resume. Compare it against this JOB DESCRIPTION requirement-by-requirement.

CANDIDATE PROFILE (JSON):
{profile_json}

JOB DESCRIPTION:
{job_description}

Steps:
1. Read the ENTIRE job description and break it down into 5-10 distinct requirements/responsibilities
   covering required skills, domain experience, scope/scale, seniority, and leadership expectations.
   Do not just scan for skill names — capture the underlying responsibility or capability.
2. For EACH requirement, classify it against the candidate profile:
   - "Met": clearly demonstrated in the profile's roles/bullets/skills (even with different tools or terminology)
   - "Partial": adjacent/related experience exists but doesn't fully cover it
   - "Missing": no evidence at all in the profile
3. For "Met" items, cite the specific evidence (which role/bullet/skill demonstrates it).
4. For "Partial"/"Missing" items, write a specific, realistic suggested_edit — an actual resume bullet
   the candidate could add or rewrite, grounded in their real background, quantified where plausible.
5. Give an overall career_alignment_score (0-100), a seniority_fit assessment, and strategic_advice
   for how to position/apply for this role.

Return ONLY a valid JSON object matching this exact schema:
{{
  "career_alignment_score": 82.0,
  "seniority_fit": "Strong fit (5+ years engineering lead vs 4+ required)",
  "requirement_matches": [
    {{"requirement": "5+ years building distributed backend systems", "status": "Met", "evidence": "Led design of microservices platform at Acme Corp", "suggested_edit": null}},
    {{"requirement": "Experience with Kubernetes at scale", "status": "Missing", "evidence": null, "suggested_edit": "Orchestrated multi-cloud Kubernetes clusters (EKS + GKE) to support 99.99% uptime for customer-facing services"}}
  ],
  "strategic_advice": "Your background in cloud microservices is a strong match. Highlight your system design leadership in your cover letter."
}}
"""


def match_resume_to_jd(
    profile: dict,
    job_description: str,
    api_key: Optional[str] = None,
    provider: str = "auto"
) -> LLMExperienceAnalysisResult:
    """Compare a previously-extracted resume profile against a JD, requirement-by-requirement."""
    llm, provider_used = _resolve_llm(api_key, provider)

    if llm:
        try:
            prompt = MATCH_PROMPT.format(
                profile_json=json.dumps(profile)[:8000],
                job_description=job_description[:6000]
            )
            response = llm.invoke(prompt)
            data = _parse_json_response(_extract_text(response.content))
            matches = data.get("requirement_matches", [])
            return _build_result_from_matches(
                is_llm_powered=True,
                provider_used=provider_used,
                career_alignment_score=float(data.get("career_alignment_score", 75.0)),
                seniority_fit=data.get("seniority_fit", "Aligned with job level"),
                strategic_advice=data.get("strategic_advice", ""),
                matches=matches,
            )
        except Exception as err:
            logger.error(f"LLM requirement matching failed: {err}")

    return heuristic_requirement_match(profile, job_description)


def _build_result_from_matches(
    is_llm_powered: bool,
    provider_used: str,
    career_alignment_score: float,
    seniority_fit: str,
    strategic_advice: str,
    matches: List[Dict[str, Any]],
) -> LLMExperienceAnalysisResult:
    """Derive the legacy list-shaped fields from the requirement_matches matrix."""
    responsibility_overlap = [
        f"{m.get('requirement', '')} — {m.get('evidence')}" if m.get("evidence") else m.get("requirement", "")
        for m in matches if m.get("status") == "Met"
    ]
    experience_gaps = [m.get("requirement", "") for m in matches if m.get("status") in ("Partial", "Missing")]
    resume_additions = [m.get("suggested_edit") for m in matches if m.get("suggested_edit")]

    return LLMExperienceAnalysisResult(
        is_llm_powered=is_llm_powered,
        provider_used=provider_used,
        career_alignment_score=career_alignment_score,
        seniority_fit=seniority_fit,
        requirement_matches=matches,
        responsibility_overlap=responsibility_overlap[:6] or ["Core software development and project execution background."],
        experience_gaps=experience_gaps[:6] or ["Ensure all quantitative achievements and scale metrics are prominently featured."],
        tailored_bullet_rewrites=resume_additions[:4],
        resume_additions=resume_additions[:6] or [
            "Add a bullet quantifying the scale and impact of your work (e.g. 'Improved efficiency by X%', 'Led team of Y engineers')."
        ],
        strategic_advice=strategic_advice or "Tailor your resume bullets to mirror the language of the job description where your experience genuinely supports it.",
    )


def heuristic_requirement_match(profile: dict, jd_text: str) -> LLMExperienceAnalysisResult:
    """Non-LLM fallback: word-overlap scoring of JD requirement sentences against the profile."""
    profile_blob = " ".join([
        profile.get("summary", ""),
        " ".join(profile.get("skills", [])),
        " ".join(profile.get("domains", [])),
        " ".join(profile.get("key_achievements", [])),
        " ".join(b for role in profile.get("roles", []) for b in role.get("bullets", [])),
    ]).lower()

    jd_sentences = [s.strip() for s in jd_text.split(".") if len(s.strip()) > 20][:8]

    matches = []
    for sentence in jd_sentences:
        words = [w for w in sentence.lower().split() if len(w) > 4]
        match_count = sum(1 for w in words if w in profile_blob)
        ratio = (match_count / len(words)) if words else 0

        if ratio >= 0.5:
            status = "Met"
            evidence = "Overlapping terms found across your resume's skills/experience bullets."
            suggested_edit = None
        elif ratio >= 0.2:
            status = "Partial"
            evidence = None
            suggested_edit = (
                f"Reframe a relevant past project to explicitly call out: '{sentence[:110]}' "
                f"— quantify the impact (e.g. 'Improved X by Y%')."
            )
        else:
            status = "Missing"
            evidence = None
            suggested_edit = (
                f"Add a bullet demonstrating experience with: '{sentence[:110]}' — "
                f"reframe a past project to highlight this responsibility and quantify the impact."
            )

        matches.append({
            "requirement": sentence[:150],
            "status": status,
            "evidence": evidence,
            "suggested_edit": suggested_edit,
        })

    if not matches:
        matches = [{
            "requirement": "General role fit",
            "status": "Partial",
            "evidence": None,
            "suggested_edit": "Quantify your past achievements (e.g. 'Improved efficiency by X%', 'Led team of Y engineers').",
        }]

    return _build_result_from_matches(
        is_llm_powered=False,
        provider_used="Rule Engine (Add API Key in Settings for Deep LLM Analysis)",
        career_alignment_score=70.0,
        seniority_fit="Moderate alignment — Review key responsibility gaps",
        strategic_advice="To get deep AI-powered work experience evaluations, add your Gemini, OpenAI, or Groq API Key in the extension settings!",
        matches=matches,
    )

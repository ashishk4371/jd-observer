import os
import json
import logging
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field

# Import LangChain provider integrations
from langchain_core.prompts import PromptTemplate

logger = logging.getLogger(__name__)

class LLMExperienceAnalysisResult(BaseModel):
    is_llm_powered: bool = True
    provider_used: str = "gemini"
    career_alignment_score: float = Field(..., description="Alignment score between 0 and 100")
    seniority_fit: str = Field(..., description="Seniority and level fit analysis (e.g. Well-aligned)")
    responsibility_overlap: List[str] = Field(..., description="Responsibilities in JD already demonstrated in resume")
    experience_gaps: List[str] = Field(..., description="Key responsibilities/experiences required by JD but missing in resume")
    tailored_bullet_rewrites: List[str] = Field(..., description="Specific bullet points rephrasing past work experience to match JD")
    strategic_advice: str = Field(..., description="Strategic application, cover letter, and interview advice")


LLM_ANALYSIS_PROMPT = """
You are an expert Executive Career Coach and ATS Hiring Specialist. 
Analyze the candidate's FULL RESUME against the target JOB DESCRIPTION.

Do NOT focus just on tech keywords. Perform a deep work experience alignment evaluation:
1. Does this JD align with the candidate's career level, title trajectory, and work history?
2. What core responsibilities in the JD are already demonstrated in their past work experience?
3. What key work experience areas or responsibilities are missing or under-represented in the resume?
4. What specific past bullet points or achievements should the candidate expand, rephrase, or add to better reflect the target JD?
5. Strategic advice on framing their background.

RESUME:
{resume_text}

JOB DESCRIPTION:
{job_description}

Return ONLY a valid JSON object matching this exact schema:
{{
  "career_alignment_score": 85.0,
  "seniority_fit": "Strong fit (5+ years engineering lead vs 4+ required)",
  "responsibility_overlap": [
    "Led cross-functional software teams to deliver distributed systems",
    "Designed and maintained CI/CD automated deployment pipelines"
  ],
  "experience_gaps": [
    "No explicit experience managing multi-cloud Kubernetes clusters",
    "Lacks documented experience with real-time streaming pipelines (Kafka)"
  ],
  "tailored_bullet_rewrites": [
    "Architected high-throughput microservices handling 10k req/sec, directly aligning with JD's scalable cloud architecture focus",
    "Spearheaded automated testing and CI/CD releases on AWS, reducing deployment errors by 40%"
  ],
  "strategic_advice": "Your background in cloud microservices is a strong match. Highlight your system design leadership in your cover letter and prepare to discuss performance optimization metrics during interviews."
}}
"""

def analyze_experience_with_llm(
    resume_text: str,
    job_description: str,
    api_key: Optional[str] = None,
    provider: str = "auto"
) -> LLMExperienceAnalysisResult:
    """
    Perform deep LLM work experience evaluation using Gemini, OpenAI, or Groq.
    Falls back gracefully to intelligent rules-based response if no key is available.
    """
    # Resolve API Key & Provider
    gemini_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    openai_key = api_key or os.getenv("OPENAI_API_KEY")
    groq_key = api_key or os.getenv("GROQ_API_KEY")

    llm = None
    provider_used = "rule_engine"

    # Try Gemini API
    if (provider in ["auto", "gemini"]) and gemini_key:
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
            llm = ChatGoogleGenerativeAI(
                model="gemini-2.5-flash" if "2.5" in str(gemini_key) else "gemini-1.5-flash",
                google_api_key=gemini_key,
                temperature=0.2
            )
            provider_used = "Gemini AI"
        except Exception as e:
            logger.warning(f"Failed to initialize Gemini LLM: {e}")

    # Try OpenAI API
    if not llm and (provider in ["auto", "openai"]) and openai_key:
        try:
            from langchain_openai import ChatOpenAI
            llm = ChatOpenAI(
                model="gpt-4o-mini",
                api_key=openai_key,
                temperature=0.2
            )
            provider_used = "OpenAI GPT-4o"
        except Exception as e:
            logger.warning(f"Failed to initialize OpenAI LLM: {e}")

    # Try Groq API
    if not llm and (provider in ["auto", "groq"]) and groq_key:
        try:
            from langchain_groq import ChatGroq
            llm = ChatGroq(
                model="llama-3.3-70b-versatile",
                groq_api_key=groq_key,
                temperature=0.2
            )
            provider_used = "Groq Llama 3.3"
        except Exception as e:
            logger.warning(f"Failed to initialize Groq LLM: {e}")

    # If LLM model is active, run completion
    if llm:
        try:
            prompt = LLM_ANALYSIS_PROMPT.format(
                resume_text=resume_text[:4000],
                job_description=job_description[:4000]
            )
            response = llm.invoke(prompt)
            raw_text = response.content.strip()

            # Clean JSON codeblock wrappers if present
            if raw_text.startswith("```"):
                raw_text = raw_text.split("```")[1]
                if raw_text.startswith("json"):
                    raw_text = raw_text[4:].strip()

            data = json.loads(raw_text)
            return LLMExperienceAnalysisResult(
                is_llm_powered=True,
                provider_used=provider_used,
                career_alignment_score=float(data.get("career_alignment_score", 75.0)),
                seniority_fit=data.get("seniority_fit", "Aligned with job level"),
                responsibility_overlap=data.get("responsibility_overlap", []),
                experience_gaps=data.get("experience_gaps", []),
                tailored_bullet_rewrites=data.get("tailored_bullet_rewrites", []),
                strategic_advice=data.get("strategic_advice", "")
            )
        except Exception as err:
            logger.error(f"LLM execution or JSON parsing failed: {err}")

    # Fallback Intelligent Rules Engine for Experience Analysis
    return fallback_experience_analysis(resume_text, job_description)


def fallback_experience_analysis(resume_text: str, jd_text: str) -> LLMExperienceAnalysisResult:
    """Generate structured experience analysis using heuristic evaluation when no LLM key is configured."""
    r_lower = resume_text.lower()
    j_lower = jd_text.lower()

    # Extract responsibilities / action verb phrases from JD
    jd_sentences = [s.strip() for s in jd_text.split(".") if len(s.strip()) > 20]
    
    overlap = []
    gaps = []

    for sentence in jd_sentences[:8]:
        words = [w for w in sentence.lower().split() if len(w) > 4]
        match_count = sum(1 for w in words if w in r_lower)
        if match_count >= 2:
            overlap.append(sentence[:120])
        else:
            gaps.append(f"Requires experience in: '{sentence[:100]}...'")

    if not overlap:
        overlap = ["Core software development and project execution background."]
    if not gaps:
        gaps = ["Ensure all quantitative achievements and scale metrics are prominently featured."]

    rewrites = [
        f"Rephrase your recent work experience to emphasize impact matching: '{gaps[0] if gaps else 'JD core responsibilities'}'",
        "Quantify your past achievements (e.g. 'Improved efficiency by X%', 'Led team of Y engineers')."
    ]

    return LLMExperienceAnalysisResult(
        is_llm_powered=False,
        provider_used="Rule Engine (Add API Key in Settings for Deep LLM Analysis)",
        career_alignment_score=70.0,
        seniority_fit="Moderate alignment — Review key responsibility gaps",
        responsibility_overlap=overlap[:4],
        experience_gaps=gaps[:4],
        tailored_bullet_rewrites=rewrites,
        strategic_advice="To get deep AI-powered work experience evaluations, add your Gemini, OpenAI, or Groq API Key in the extension settings!"
    )

def extract_requirements_from_job_description(job_desc: str) -> Dict[str, List[str]]:
    # Code to parse and extract requirements from job description
    pass

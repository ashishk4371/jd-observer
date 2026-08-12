import hashlib
import re
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

load_dotenv()

from .models import (
    ResumeUploadResponse,
    AnalyzeRequest,
    AnalyzeResponse,
    MatchCategoryBreakdown,
    SkillMatchDetail,
    ExperienceMatchDetail,
    LLMExperienceAnalysis,
    ResumeProfile,
    ResumeListItem,
    ResumeListResponse,
    CompareResumesRequest,
    CompareResumesResponse,
    RankedResumeResult,
)
from . import db
from .embeddings import embed_text
from .extractor import extract_text_from_file, extract_skills
from .similarity import compute_similarity_metrics
from .llm import build_resume_profile, match_resume_to_jd


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def get_or_create_resume(text: str, filename: str = "resume.txt") -> Dict[str, Any]:
    """Look up a resume row by content hash, or insert a new one. Content-hash keyed,
    so re-submitting the same resume text (even via a different upload) reuses the row."""
    h = content_hash(text)
    existing = db.get_resume_by_hash(h)
    if existing:
        return existing
    resume_id = db.insert_resume(filename=filename, content_hash=h, raw_text=text)
    return db.get_resume(resume_id)


def get_or_build_profile(resume_row: Dict[str, Any], api_key: Optional[str], provider: str) -> Dict[str, Any]:
    """Look up a cached profile by the resume's content hash, or build + persist one
    (including its embedding vector) if this resume hasn't been profiled before."""
    profile = db.get_profile_by_content_hash(resume_row["content_hash"])
    if profile:
        return profile

    profile_result = build_resume_profile(resume_row["raw_text"], api_key=api_key, provider=provider)
    profile_dict = profile_result.model_dump()
    profile_id = db.insert_profile(resume_row["id"], resume_row["content_hash"], profile_dict)

    embedding_text = " ".join([
        profile_dict.get("summary", ""),
        " ".join(profile_dict.get("skills", [])),
        " ".join(profile_dict.get("domains", [])),
        " ".join(profile_dict.get("key_achievements", [])),
    ])
    vector = embed_text(embedding_text)
    if vector is not None:
        db.upsert_resume_profile_vector(profile_id, vector)

    profile_dict["id"] = profile_id
    return profile_dict


def get_or_embed_job_description(text: str) -> Dict[str, Any]:
    """Look up a job description row by content hash, or insert one and embed it."""
    h = content_hash(text)
    existing = db.get_job_description_by_hash(h)
    if existing:
        return existing

    jd_id = db.insert_job_description(text=text, content_hash=h)
    vector = embed_text(text)
    if vector is not None:
        db.upsert_job_description_vector(jd_id, vector)
    return db.get_job_description_by_hash(h)

app = FastAPI(
    title="Job Description Analyzer API",
    description="Backend API for Job Description Analyzer Chrome Extension",
    version="1.1.0"
)

# Enable CORS for browser extension and localhost clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows extension and local dev origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "Job Description Analyzer API"}


@app.post("/upload_resume", response_model=ResumeUploadResponse)
async def upload_resume(
    file: UploadFile = File(...),
    api_key: Optional[str] = Form(None),
    provider: Optional[str] = Form("auto"),
):
    fname = file.filename or "resume.txt"
    if not fname.lower().endswith((".txt", ".pdf", ".docx")):
        raise HTTPException(
            status_code=400,
            detail="Unsupported format. Supported extensions: .pdf, .docx, .txt"
        )
    try:
        content_bytes = await file.read()
        extracted_text = extract_text_from_file(content_bytes, fname)
    except Exception as e:
        raise HTTPException(
            status_code=422,
            detail=f"Failed to parse document content: {str(e)}"
        )

    if not extracted_text.strip():
        raise HTTPException(
            status_code=400,
            detail="Extracted resume content is empty or unreadable."
        )

    resume_row = get_or_create_resume(extracted_text, filename=fname)
    skills = extract_skills(extracted_text)

    # Build (or reuse a DB-cached) structured profile so repeated JD comparisons
    # against this resume don't need to re-derive its content from scratch each time.
    profile_dict = get_or_build_profile(resume_row, api_key=api_key, provider=provider or "auto")

    return ResumeUploadResponse(
        resume_id=resume_row["id"],
        filename=fname,
        extracted_text_length=len(extracted_text),
        parsed_skills_count=len(skills),
        message="Resume uploaded and parsed successfully!",
        resume_profile=ResumeProfile(**profile_dict)
    )


def run_analysis(
    resume_row: Dict[str, Any],
    jd_row: Dict[str, Any],
    api_key: Optional[str],
    provider: str,
) -> AnalyzeResponse:
    """The full holistic pipeline for one resume against one job description:
    keyword/embedding similarity + LLM requirement matching, blended into a score,
    persisted as an analyses row. Shared by /analyze (one resume) and /compare
    (many resumes against the same JD, one run_analysis call each)."""
    resume_text = resume_row["raw_text"]

    # 1. Resolve the resume's structured profile (cached when resume_id was uploaded
    # via /upload_resume; built on the fly otherwise) and both embeddings.
    profile_dict = get_or_build_profile(resume_row, api_key=api_key, provider=provider)
    resume_vector = db.get_resume_profile_vector(profile_dict["id"])
    jd_vector = db.get_job_description_vector(jd_row["id"])

    # 2. Compute Base Keyword & Semantic Similarity (embedding-based when available)
    metrics = compute_similarity_metrics(
        resume_text,
        jd_row["text"],
        resume_embedding=resume_vector,
        jd_embedding=jd_vector,
    )
    score = metrics["overall_score"]

    llm_res = match_resume_to_jd(
        profile=profile_dict,
        job_description=jd_row["text"],
        api_key=api_key,
        provider=provider
    )

    if llm_res.is_llm_powered:
        # If LLM model produced a deep alignment score, weight it into overall score
        score = round((0.6 * score) + (0.4 * llm_res.career_alignment_score), 1)

    if score >= 80.0:
        level = "Excellent"
    elif score >= 65.0:
        level = "Good"
    elif score >= 45.0:
        level = "Moderate"
    else:
        level = "Needs Tailoring"

    # Human readable summary
    missing = metrics["missing_skills"]
    missing_str = ", ".join(missing[:5]) if missing else "None"
    summary = (
        f"Match Score: {score:.1f}% ({level}). "
        f"Seniority Fit: {llm_res.seniority_fit}. "
        f"Missing key skills: {missing_str}."
    )

    actionable_tips = []
    if llm_res.strategic_advice:
        actionable_tips.append(llm_res.strategic_advice)
    if missing:
        actionable_tips.append(f"Add key missing technologies: {', '.join(missing[:4])}")
    if metrics["experience_gap"]:
        actionable_tips.append(metrics["experience_gap"])

    response = AnalyzeResponse(
        match_score=score,
        score_level=level,
        breakdown=MatchCategoryBreakdown(
            overall_score=score,
            keyword_similarity=metrics["keyword_similarity"],
            semantic_similarity=metrics["semantic_similarity"],
            skill_coverage=metrics["skill_coverage"],
        ),
        skills=SkillMatchDetail(
            matched_skills=metrics["matched_skills"],
            missing_skills=metrics["missing_skills"],
            skill_match_percentage=metrics["skill_coverage"],
            suggested_additions=metrics["suggested_additions"],
        ),
        experience=ExperienceMatchDetail(
            resume_total_years=metrics["resume_years"],
            jd_required_years=metrics["jd_years"],
            experience_gap=metrics["experience_gap"],
            rewrite_suggestions=llm_res.tailored_bullet_rewrites or metrics["rewrite_suggestions"],
        ),
        llm_analysis=LLMExperienceAnalysis(
            is_llm_powered=llm_res.is_llm_powered,
            provider_used=llm_res.provider_used,
            career_alignment_score=llm_res.career_alignment_score,
            requirement_matches=llm_res.requirement_matches,
            seniority_fit=llm_res.seniority_fit,
            responsibility_overlap=llm_res.responsibility_overlap,
            experience_gaps=llm_res.experience_gaps,
            tailored_bullet_rewrites=llm_res.tailored_bullet_rewrites,
            resume_additions=llm_res.resume_additions,
            strategic_advice=llm_res.strategic_advice
        ),
        summary=summary,
        actionable_tips=actionable_tips,
    )

    # Persist this analysis run as history (foundation for future application tracking).
    db.insert_analysis(
        resume_id=resume_row["id"],
        job_description_id=jd_row["id"],
        match_score=response.match_score,
        score_level=response.score_level,
        breakdown=response.breakdown.model_dump(),
        skills=response.skills.model_dump(),
        llm_analysis=response.llm_analysis.model_dump(),
        summary=response.summary,
        actionable_tips=response.actionable_tips,
    )

    return response


@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze(request: AnalyzeRequest):
    resume_row = None
    if request.resume_id:
        resume_row = db.get_resume(request.resume_id)

    if resume_row is None and request.resume_text:
        resume_row = get_or_create_resume(request.resume_text)

    if resume_row is None:
        raise HTTPException(
            status_code=400,
            detail="Resume text is required. Please provide a valid resume_id or resume_text."
        )

    if not request.job_description.strip():
        raise HTTPException(
            status_code=400,
            detail="Job description text is empty."
        )

    jd_row = get_or_embed_job_description(request.job_description)
    return run_analysis(resume_row, jd_row, api_key=request.api_key, provider=request.provider or "auto")


@app.post("/analyze_direct", response_model=AnalyzeResponse)
async def analyze_direct(
    job_description: str = Form(...),
    file: UploadFile = File(...),
    api_key: Optional[str] = Form(None)
):
    fname = file.filename or "resume.pdf"
    content_bytes = await file.read()
    resume_text = extract_text_from_file(content_bytes, fname)

    return await analyze(AnalyzeRequest(
        resume_text=resume_text,
        job_description=job_description,
        api_key=api_key
    ))


@app.get("/resumes", response_model=ResumeListResponse)
async def list_resumes():
    """The resume library — every resume ever uploaded, durable across restarts."""
    items = []
    for row in db.list_resumes():
        profile = db.get_profile_by_content_hash(row["content_hash"])
        items.append(ResumeListItem(
            resume_id=row["id"],
            filename=row["filename"],
            uploaded_at=row["uploaded_at"],
            seniority_level=profile["seniority_level"] if profile else None,
            summary=profile["summary"] if profile else None,
        ))
    return ResumeListResponse(resumes=items)


@app.delete("/resumes/{resume_id}")
async def remove_resume(resume_id: str):
    if db.get_resume(resume_id) is None:
        raise HTTPException(status_code=404, detail="Resume not found.")
    db.delete_resume(resume_id)
    return {"status": "deleted", "resume_id": resume_id}


@app.post("/compare", response_model=CompareResumesResponse)
async def compare_resumes(request: CompareResumesRequest):
    """Rank multiple resumes against one job description using the same holistic
    pipeline as /analyze (embedding similarity + LLM requirement matching) for
    each — not a cheap keyword-only pre-rank."""
    if not request.resume_ids:
        raise HTTPException(status_code=400, detail="At least one resume_id is required.")
    if not request.job_description.strip():
        raise HTTPException(status_code=400, detail="Job description text is empty.")

    # The JD is embedded once and reused for every resume in the comparison.
    jd_row = get_or_embed_job_description(request.job_description)
    provider = request.provider or "auto"

    results = []
    for resume_id in request.resume_ids:
        resume_row = db.get_resume(resume_id)
        if resume_row is None:
            continue  # skip unknown ids rather than fail the whole comparison
        analysis = run_analysis(resume_row, jd_row, api_key=request.api_key, provider=provider)
        results.append(RankedResumeResult(
            resume_id=resume_row["id"],
            filename=resume_row["filename"],
            analysis=analysis,
        ))

    results.sort(key=lambda r: r.analysis.match_score, reverse=True)
    return CompareResumesResponse(results=results)


def main():
    """CLI entry point to launch uvicorn server."""
    import uvicorn
    uvicorn.run("jd_analyzer.main:app", host="127.0.0.1", port=8000, reload=True)


if __name__ == "__main__":
    main()
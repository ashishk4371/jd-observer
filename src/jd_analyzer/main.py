import re
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .models import (
    ResumeUploadResponse,
    AnalyzeRequest,
    AnalyzeResponse,
    MatchCategoryBreakdown,
    SkillMatchDetail,
    ExperienceMatchDetail,
    LLMExperienceAnalysis,
)
from .resume_store import resume_store
from .extractor import extract_text_from_file, extract_skills
from .similarity import compute_similarity_metrics
from .llm import analyze_experience_with_llm

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
async def upload_resume(file: UploadFile = File(...)):
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

    rid = resume_store.add(extracted_text, filename=fname)
    skills = extract_skills(extracted_text)

    return ResumeUploadResponse(
        resume_id=rid,
        filename=fname,
        extracted_text_length=len(extracted_text),
        parsed_skills_count=len(skills),
        message="Resume uploaded and parsed successfully!"
    )


@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze(request: AnalyzeRequest):
    resume_text = ""
    if request.resume_id:
        stored = resume_store.get(request.resume_id)
        if stored:
            resume_text = stored

    if not resume_text and request.resume_text:
        resume_text = request.resume_text

    if not resume_text.strip():
        raise HTTPException(
            status_code=400,
            detail="Resume text is required. Please provide a valid resume_id or resume_text."
        )

    if not request.job_description.strip():
        raise HTTPException(
            status_code=400,
            detail="Job description text is empty."
        )

    # 1. Compute Base Keyword & Vector Similarity
    metrics = compute_similarity_metrics(resume_text, request.job_description)
    score = metrics["overall_score"]

    # 2. Perform Deep LLM Experience Evaluation
    llm_res = analyze_experience_with_llm(
        resume_text=resume_text,
        job_description=request.job_description,
        api_key=request.api_key,
        provider=request.provider or "auto"
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
            seniority_fit=llm_res.seniority_fit,
            responsibility_overlap=llm_res.responsibility_overlap,
            experience_gaps=llm_res.experience_gaps,
            tailored_bullet_rewrites=llm_res.tailored_bullet_rewrites,
            strategic_advice=llm_res.strategic_advice
        ),
        summary=summary,
        actionable_tips=actionable_tips,
    )
    return response


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


def main():
    """CLI entry point to launch uvicorn server."""
    import uvicorn
    uvicorn.run("jd_analyzer.main:app", host="127.0.0.1", port=8000, reload=True)


if __name__ == "__main__":
    main()
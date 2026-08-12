from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any, Literal

class ResumeRole(BaseModel):
    title: str
    company: Optional[str] = None
    duration: Optional[str] = None
    bullets: List[str] = []

class ResumeProfile(BaseModel):
    summary: str
    seniority_level: str
    total_years_experience: Optional[float] = None
    skills: List[str] = []
    domains: List[str] = []
    roles: List[ResumeRole] = []
    key_achievements: List[str] = []
    is_llm_powered: bool = False

class RequirementMatch(BaseModel):
    requirement: str
    status: Literal["Met", "Partial", "Missing"]
    evidence: Optional[str] = None
    suggested_edit: Optional[str] = None

class ResumeUploadResponse(BaseModel):
    resume_id: str
    filename: str
    extracted_text_length: int
    parsed_skills_count: int
    message: str
    resume_profile: Optional[ResumeProfile] = None

class AnalyzeRequest(BaseModel):
    resume_id: Optional[str] = None
    resume_text: Optional[str] = None
    job_description: str
    api_key: Optional[str] = None
    provider: Optional[str] = "auto"

class SkillMatchDetail(BaseModel):
    matched_skills: List[str]
    missing_skills: List[str]
    skill_match_percentage: float
    suggested_additions: List[str]

class ExperienceMatchDetail(BaseModel):
    resume_total_years: Optional[float]
    jd_required_years: Optional[float]
    experience_gap: Optional[str]
    rewrite_suggestions: List[str]

class MatchCategoryBreakdown(BaseModel):
    overall_score: float        # 0 - 100
    keyword_similarity: float   # 0 - 100
    semantic_similarity: float  # 0 - 100
    skill_coverage: float       # 0 - 100

class LLMExperienceAnalysis(BaseModel):
    is_llm_powered: bool = False
    provider_used: str = "Rule Engine"
    career_alignment_score: float = 70.0
    seniority_fit: str = ""
    responsibility_overlap: List[str] = []
    experience_gaps: List[str] = []
    tailored_bullet_rewrites: List[str] = []
    resume_additions: List[str] = []
    strategic_advice: str = ""
    requirement_matches: List[RequirementMatch] = []

class AnalyzeResponse(BaseModel):
    match_score: float          # 0 - 100
    score_level: str            # 'Excellent', 'Good', 'Moderate', 'Low'
    breakdown: MatchCategoryBreakdown
    skills: SkillMatchDetail
    experience: ExperienceMatchDetail
    llm_analysis: Optional[LLMExperienceAnalysis] = None
    summary: str
    actionable_tips: List[str]

class ResumeListItem(BaseModel):
    resume_id: str
    filename: str
    uploaded_at: str
    seniority_level: Optional[str] = None
    summary: Optional[str] = None

class ResumeListResponse(BaseModel):
    resumes: List[ResumeListItem]

class CompareResumesRequest(BaseModel):
    resume_ids: List[str]
    job_description: str
    api_key: Optional[str] = None
    provider: Optional[str] = "auto"

class RankedResumeResult(BaseModel):
    resume_id: str
    filename: str
    analysis: AnalyzeResponse

class CompareResumesResponse(BaseModel):
    results: List[RankedResumeResult]
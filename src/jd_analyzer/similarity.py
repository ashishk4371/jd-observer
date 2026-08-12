import re
import numpy as np
from typing import Tuple, Dict, List, Optional
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from .extractor import extract_skills, extract_years_of_experience
from .embeddings import cosine_similarity_score

def compute_similarity_metrics(
    resume_text: str,
    jd_text: str,
    resume_embedding: Optional[bytes] = None,
    jd_embedding: Optional[bytes] = None,
) -> Dict:
    """
    Computes a comprehensive matching score combining:
    1. TF-IDF Cosine Similarity (Semantic & N-gram matching)
    2. Skill Match Coverage (JD skills present in Resume)
    3. Keyword Overlap (Jaccard similarity on clean tokens)
    4. Experience Requirement Evaluation
    """
    # Clean texts
    r_text = resume_text.strip()
    j_text = jd_text.strip()

    if not r_text or not j_text:
        return {
            "overall_score": 0.0,
            "keyword_similarity": 0.0,
            "semantic_similarity": 0.0,
            "skill_coverage": 0.0,
            "matched_skills": [],
            "missing_skills": [],
            "suggested_additions": [],
            "resume_years": None,
            "jd_years": None,
            "experience_gap": None,
            "rewrite_suggestions": []
        }

    # 1. Semantic Similarity — embedding-based cosine similarity when both vectors
    # are available (upgrade), otherwise fall back to TF-IDF n-gram cosine similarity.
    if resume_embedding is not None and jd_embedding is not None:
        sem_sim = cosine_similarity_score(resume_embedding, jd_embedding)
    else:
        vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2))
        tfidf_matrix = vectorizer.fit_transform([r_text, j_text])
        sem_sim = float(cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]) * 100.0

    # 2. Skill Extraction & Coverage
    resume_skills = set(extract_skills(r_text))
    jd_skills = set(extract_skills(j_text))

    matched_skills = sorted(list(jd_skills & resume_skills))
    missing_skills = sorted(list(jd_skills - resume_skills))

    if jd_skills:
        skill_coverage = (len(matched_skills) / len(jd_skills)) * 100.0
    else:
        skill_coverage = 70.0  # default baseline if JD explicitly mentions no specific tech stack skills

    # 3. Keyword Overlap (Jaccard)
    r_words = set(re.findall(r"\b[a-z]{3,}\b", r_text.lower()))
    j_words = set(re.findall(r"\b[a-z]{3,}\b", j_text.lower()))
    
    if j_words:
        kw_similarity = (len(r_words & j_words) / len(j_words)) * 100.0
    else:
        kw_similarity = 50.0

    # 4. Experience Gap
    resume_years = extract_years_of_experience(r_text)
    jd_years = extract_years_of_experience(j_text)

    experience_gap = None
    rewrite_suggestions = []

    if jd_years:
        if resume_years is None or resume_years < jd_years:
            experience_gap = f"The job requires ~{int(jd_years)} year(s) of experience. Ensure your timeline & senior responsibilities are clearly specified."
            rewrite_suggestions.append(f"Highlight lead responsibilities and quantify impact matching {int(jd_years)}+ years experience.")
        else:
            experience_gap = f"Your resume indicates sufficient experience (~{int(resume_years)} yrs vs required {int(jd_years)} yrs)."

    # 5. Suggested additions for missing skills
    suggested_additions = [
        f"Add '{skill}' to your Technical Skills section or project descriptions."
        for skill in missing_skills[:8]
    ]

    # Generate tailored resume bullet point rewrite examples
    if missing_skills:
        top_missing = missing_skills[:3]
        for skill in top_missing:
            rewrite_suggestions.append(
                f"Leveraged {skill} to design and implement scalable application modules, enhancing performance by 25%."
            )

    # 6. Overall Weighted Score Calculation
    # Weights: 45% Skill Coverage, 35% TF-IDF Similarity, 20% Keyword Overlap
    overall_score = (0.45 * skill_coverage) + (0.35 * sem_sim) + (0.20 * kw_similarity)
    overall_score = min(100.0, max(0.0, round(overall_score, 1)))

    return {
        "overall_score": overall_score,
        "keyword_similarity": round(kw_similarity, 1),
        "semantic_similarity": round(sem_sim, 1),
        "skill_coverage": round(skill_coverage, 1),
        "matched_skills": matched_skills,
        "missing_skills": missing_skills,
        "suggested_additions": suggested_additions,
        "resume_years": resume_years,
        "jd_years": jd_years,
        "experience_gap": experience_gap,
        "rewrite_suggestions": rewrite_suggestions,
    }
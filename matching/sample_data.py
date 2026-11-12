"""Synthetic sample candidates, loaded into the DB by `seed_sample_data`. No real candidate data."""

SEED_USERNAME = "sample_seed"  # inactive system user that owns the shared sample search
SAMPLE_JOB_TITLE = "Data Engineer"
SAMPLE_JOB_SKILLS = ["Python", "SQL", "Spark", "Azure"]

# external_id, candidate_ref, name, role, years, score (0-100 for the sample job), skills, summary
SAMPLE_CANDIDATES = [
    {
        "external_id": "r_104", "candidate_ref": "CAND-0104", "name": "Candidate A", "role": "Data Engineer",
        "years": 8, "score": 91, "skills": ["Python", "SQL", "Spark", "Azure"],
        "summary": "Built Spark batch and streaming pipelines on Azure Databricks for commercial analytics.",
    },
    {
        "external_id": "r_087", "candidate_ref": "CAND-0087", "name": "Candidate B", "role": "Analytics Engineer",
        "years": 6, "score": 84, "skills": ["Python", "Azure", "SQL"],
        "summary": "Designed ELT models and orchestration on Azure Data Factory.",
    },
    {
        "external_id": "r_142", "candidate_ref": "CAND-0142", "name": "Candidate C", "role": "Software Engineer",
        "years": 5, "score": 73, "skills": ["Python", "SQL"],
        "summary": "Backend services and reporting APIs in Python with SQL warehouses.",
    },
    {
        "external_id": "r_019", "candidate_ref": "CAND-0019", "name": "Candidate D", "role": "Data Analyst",
        "years": 4, "score": 58, "skills": ["SQL", "Azure"],
        "summary": "Dashboards and ad-hoc analysis; started moving jobs to cloud.",
    },
]

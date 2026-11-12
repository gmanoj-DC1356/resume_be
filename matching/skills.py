"""Skill taxonomy: canonical display name -> aliases. Used to normalise and detect skills.

Starter list; extend as the knowledge base grows (tracked for Phase 2 tuning).
"""
import re

SKILLS: dict[str, list[str]] = {
    "Python": [], "SQL": [], "Spark": ["apache spark", "pyspark"], "Azure": ["microsoft azure"],
    "Databricks": ["azure databricks"], "Azure Data Factory": ["adf"], "AWS": ["amazon web services"],
    "GCP": ["google cloud"], "Java": [], "C#": ["csharp"], "C++": [], "Scala": [], "Kafka": ["apache kafka"],
    "Airflow": ["apache airflow"], "dbt": [], "Snowflake": [], "PostgreSQL": ["postgres"], "MySQL": [],
    "MongoDB": [], "Redis": [], "Docker": [], "Kubernetes": ["k8s"], "Terraform": [], "Git": [],
    "GitHub Actions": [], "Azure DevOps": ["ado"], "Jenkins": [], "REST": ["rest api", "rest apis"],
    "GraphQL": [], "Django": [], "FastAPI": [], "Flask": [], "Node.js": ["node", "nodejs"],
    "Express": ["express.js", "expressjs"], "JavaScript": ["js", "ecmascript"], "TypeScript": ["ts"],
    "React": ["react.js", "reactjs"], "Redux": ["redux toolkit"], "Next.js": ["nextjs"],
    "Angular": ["angularjs"], "RxJS": [], "NgRx": [], "Vue.js": ["vue", "vuejs", "vue 3"], "Nuxt": ["nuxt.js", "nuxt 3"],
    "Pinia": [], "Vuetify": [], "HTML": ["html5"], "CSS": ["css3"], "Sass": ["scss"],
    "Tailwind CSS": ["tailwind"], "Bootstrap": [], "Webpack": [], "Vite": [], "Storybook": [],
    "Jest": [], "Vitest": [], "Cypress": [], "Playwright": [], "Jasmine": [], "Karma": [],
    "React Testing Library": [], "Accessibility": ["a11y"], "WCAG": [], "ARIA": [], "Figma": [],
    "Design Systems": ["design system"], "Web Components": [], "Apollo": ["apollo client"],
    "Lighthouse": [], "Angular Material": [], "Nx": [], "Power BI": ["powerbi"], "Tableau": [],
    "Pandas": [], "NumPy": [], "Machine Learning": ["ml"], "ETL": [], "ELT": [],
}

_CANONICAL = {name.lower(): name.lower() for name in SKILLS}
for _name, _aliases in SKILLS.items():
    for _alias in _aliases:
        _CANONICAL[_alias.lower()] = _name.lower()

_DISPLAY = {name.lower(): name for name in SKILLS}


def normalize_skill(skill: str) -> str:
    """Lower-case, collapse whitespace, strip punctuation, map aliases to the canonical key."""
    key = re.sub(r"\s+", " ", skill.strip().lower()).strip(" .,;:()")
    return _CANONICAL.get(key, key)


def display_name(skill: str) -> str:
    return _DISPLAY.get(normalize_skill(skill), skill.strip())


def _term_regex(term: str) -> re.Pattern:
    return re.compile(r"(?<![\w+#.])" + re.escape(term) + r"(?![\w+#])", re.IGNORECASE)


_DETECTORS = [
    (name, [_term_regex(t) for t in [name, *aliases]]) for name, aliases in SKILLS.items()
]


def extract_skills(text: str) -> list[str]:
    """Taxonomy skills found anywhere in the text, in taxonomy order."""
    return [name for name, patterns in _DETECTORS if any(p.search(text) for p in patterns)]

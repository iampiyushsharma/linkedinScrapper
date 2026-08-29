class LinkedInEndpoints:
    BASE_URL = "https://www.linkedin.com"

    # Primary call: root profile + positions + educations + companies + schools
    # + geo + industry, and (capped) skills / projects / certifications.
    DASH_PROFILES = "/voyager/api/identity/dash/profiles"
    DECORATION_ID = "com.linkedin.voyager.dash.deco.identity.profile.FullProfileWithEntities-85"

    # Supplementary per-section collections, queried by the root profile URN.
    # Used to get the *complete* lists (the primary call truncates skills etc.).
    SECTION_ENDPOINTS = {
        "skills": "/voyager/api/identity/dash/profileSkills",
        "languages": "/voyager/api/identity/dash/profileLanguages",
        "certifications": "/voyager/api/identity/dash/profileCertifications",
        "volunteer": "/voyager/api/identity/dash/profileVolunteerExperiences",
        "honors": "/voyager/api/identity/dash/profileHonors",
        "projects": "/voyager/api/identity/dash/profileProjects",
    }

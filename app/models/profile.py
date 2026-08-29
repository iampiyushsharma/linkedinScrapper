from typing import List, Optional
from pydantic import BaseModel


class ProfileRequest(BaseModel):
    url: str
    # Optional per-request LinkedIn session. Overrides the server's
    # LINKEDIN_LI_AT / LINKEDIN_JSESSIONID for this call only.
    li_at: Optional[str] = None
    jsessionid: Optional[str] = None
    # When true, also fetch the complete skills / languages / certifications /
    # volunteering / honors / projects collections (6 extra sequential requests).
    # Default false = a single request (gentler on the session; the primary call
    # still returns ~20 skills plus projects and certifications inline).
    full: bool = False


class Experience(BaseModel):
    company: Optional[str] = None
    company_url: Optional[str] = None
    company_logo: Optional[str] = None
    title: Optional[str] = None
    employment_type: Optional[str] = None
    location: Optional[str] = None
    description: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    current: bool = False


class Education(BaseModel):
    institution: Optional[str] = None
    institution_url: Optional[str] = None
    institution_logo: Optional[str] = None
    degree: Optional[str] = None
    field_of_study: Optional[str] = None
    description: Optional[str] = None
    activities: Optional[str] = None
    grade: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class Skill(BaseModel):
    name: str


class Certification(BaseModel):
    name: str
    issuer: Optional[str] = None
    license_number: Optional[str] = None
    url: Optional[str] = None
    issue_date: Optional[str] = None
    expiry_date: Optional[str] = None


class Language(BaseModel):
    name: str
    proficiency: Optional[str] = None


class Project(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class Honor(BaseModel):
    title: Optional[str] = None
    issuer: Optional[str] = None
    description: Optional[str] = None
    date: Optional[str] = None


class Volunteer(BaseModel):
    organization: Optional[str] = None
    role: Optional[str] = None
    cause: Optional[str] = None
    description: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class ProfileInfo(BaseModel):
    name: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    headline: Optional[str] = None
    location: Optional[str] = None
    country: Optional[str] = None
    industry: Optional[str] = None
    about: Optional[str] = None
    public_identifier: Optional[str] = None
    profile_url: Optional[str] = None
    member_id: Optional[str] = None
    is_premium: bool = False
    is_influencer: bool = False
    profile_image: Optional[str] = None
    background_image: Optional[str] = None


class ProfileResponse(BaseModel):
    profile: ProfileInfo
    experience: List[Experience] = []
    education: List[Education] = []
    skills: List[Skill] = []
    certifications: List[Certification] = []
    languages: List[Language] = []
    projects: List[Project] = []
    honors: List[Honor] = []
    volunteer: List[Volunteer] = []

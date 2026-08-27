from typing import List, Optional
from pydantic import BaseModel

class ProfileRequest(BaseModel):
    url: str

class Experience(BaseModel):
    company: Optional[str] = None
    title: Optional[str] = None
    location: Optional[str] = None
    description: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    current: bool = False

class Education(BaseModel):
    institution: Optional[str] = None
    degree: Optional[str] = None
    field_of_study: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None

class Skill(BaseModel):
    name: str

class Certification(BaseModel):
    name: str
    issuer: Optional[str] = None
    issue_date: Optional[str] = None

class Language(BaseModel):
    name: str
    proficiency: Optional[str] = None

class ProfileInfo(BaseModel):
    name: Optional[str] = None
    headline: Optional[str] = None
    location: Optional[str] = None
    about: Optional[str] = None
    profile_url: Optional[str] = None
    profile_image: Optional[str] = None

class ProfileResponse(BaseModel):
    profile: ProfileInfo
    experience: List[Experience] = []
    education: List[Education] = []
    skills: List[Skill] = []
    certifications: List[Certification] = []
    languages: List[Language] = []

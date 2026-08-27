from typing import Dict, Any, List, Optional
from collections import defaultdict
import logging

from app.models.profile import ProfileInfo, Experience, Education, Skill, Certification, Language, ProfileResponse

logger = logging.getLogger(__name__)

class LinkedInParser:
    def __init__(self, raw_data: Dict[str, Any]):
        self.raw_data = raw_data
        self.entities_by_urn: Dict[str, Dict[str, Any]] = {}
        self.entities_by_type: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self.profile_urn: Optional[str] = None
        self._build_graph()

    def _build_graph(self):
        """Builds a lookup index of all entities by their URN."""
        included = self.raw_data.get("included", [])
        for item in included:
            urn = item.get("entityUrn")
            if urn:
                self.entities_by_urn[urn] = item
            
            # Pre-group entities by type for O(1) lookup later
            entity_type = item.get("$type")
            if entity_type:
                self.entities_by_type[entity_type].append(item)

        # Find the root profile URN from data.*elements
        data = self.raw_data.get("data") or {}
        elements = data.get("*elements", [])
        if elements:
            self.profile_urn = elements[0]

    def _get_entity(self, urn: str) -> Optional[Dict[str, Any]]:
        if not urn:
            return None
        return self.entities_by_urn.get(urn)

    def _resolve_entities(self, urns: List[str]) -> List[Dict[str, Any]]:
        return [self._get_entity(urn) for urn in urns if self._get_entity(urn)]

    def _extract_date_range(self, date_range: Dict[str, Any]) -> tuple[Optional[str], Optional[str]]:
        if not date_range or not isinstance(date_range, dict):
            return None, None
            
        def format_date(d):
            if not d: return None
            year = d.get("year")
            month = d.get("month")
            if year and month:
                return f"{year}-{month:02d}"
            if year:
                return str(year)
            return None

        start = format_date(date_range.get("start"))
        end = format_date(date_range.get("end"))
        return start, end

    def _extract_text(self, obj: Dict[str, Any], key: str = "text") -> Optional[str]:
        """Extracts text from LinkedIn's multi-locale text structures."""
        if not obj:
            return None
        # Handle cases where the text might be nested
        if isinstance(obj, str):
            return obj
        return obj.get("text") or obj.get(key)

    def parse(self) -> ProfileResponse:
        if not self.profile_urn:
            logger.error("Could not find root profile URN in response data")
            raise ValueError("Invalid LinkedIn response format")

        root_profile = self._get_entity(self.profile_urn)
        if not root_profile:
            raise ValueError("Root profile entity missing")

        return ProfileResponse(
            profile=self._parse_basic_info(root_profile),
            experience=self._parse_experience(root_profile),
            education=self._parse_education(root_profile),
            skills=self._parse_skills(root_profile),
            certifications=self._parse_certifications(root_profile),
            languages=self._parse_languages(root_profile)
        )

    def _parse_basic_info(self, profile: Dict[str, Any]) -> ProfileInfo:
        first_name = profile.get("firstName", "")
        last_name = profile.get("lastName", "")
        name = f"{first_name} {last_name}".strip()
        
        # Image URL logic - often inside picture.rootUrl + picture.artifacts[x].fileIdentifyingUrlPathSegment
        profile_image = None
        picture = profile.get("picture", {})
        if picture and isinstance(picture, dict) and "rootUrl" in picture:
            artifacts = picture.get("artifacts", [])
            if isinstance(artifacts, list) and len(artifacts) > 0:
                # Use the largest artifact
                artifact = artifacts[-1]
                if isinstance(artifact, dict):
                    profile_image = f"{picture['rootUrl']}{artifact.get('fileIdentifyingUrlPathSegment', '')}"

        return ProfileInfo(
            name=name if name else None,
            headline=profile.get("headline"),
            location=profile.get("locationName"),
            about=profile.get("summary"),
            profile_url=profile.get("publicIdentifier") and f"https://www.linkedin.com/in/{profile.get('publicIdentifier')}",
            profile_image=profile_image
        )

    def _parse_experience(self, profile: Dict[str, Any]) -> List[Experience]:
        experiences = []
        position_entities = self.entities_by_type.get("com.linkedin.voyager.dash.identity.profile.Position", [])
        
        # Sort by start date (descending) roughly
        
        for pos in position_entities:
            company_name = pos.get("companyName")
            title = pos.get("title")
            description = pos.get("description")
            location = pos.get("locationName")
            
            date_range = pos.get("dateRange", {})
            start_date, end_date = self._extract_date_range(date_range)
            
            current = end_date is None
            
            experiences.append(Experience(
                company=company_name,
                title=title,
                location=location,
                description=description,
                start_date=start_date,
                end_date=end_date,
                current=current
            ))
            
        return experiences

    def _parse_education(self, profile: Dict[str, Any]) -> List[Education]:
        educations = []
        edu_entities = self.entities_by_type.get("com.linkedin.voyager.dash.identity.profile.Education", [])
        
        for edu in edu_entities:
            institution = edu.get("schoolName")
            degree = edu.get("degreeName")
            field_of_study = edu.get("fieldOfStudy")
            
            date_range = edu.get("dateRange", {})
            start_date, end_date = self._extract_date_range(date_range)
            
            educations.append(Education(
                institution=institution,
                degree=degree,
                field_of_study=field_of_study,
                start_date=start_date,
                end_date=end_date
            ))
            
        return educations

    def _parse_skills(self, profile: Dict[str, Any]) -> List[Skill]:
        skills = []
        skill_entities = self.entities_by_type.get("com.linkedin.voyager.dash.identity.profile.Skill", [])
        
        for skill in skill_entities:
            name = skill.get("name")
            if name:
                skills.append(Skill(name=name))
                
        return skills

    def _parse_certifications(self, profile: Dict[str, Any]) -> List[Certification]:
        certs = []
        cert_entities = self.entities_by_type.get("com.linkedin.voyager.dash.identity.profile.Certification", [])
        
        for cert in cert_entities:
            name = cert.get("name")
            issuer = cert.get("authority")
            
            date_range = cert.get("dateRange", {})
            issue_date, _ = self._extract_date_range(date_range)
            
            if name:
                certs.append(Certification(
                    name=name,
                    issuer=issuer,
                    issue_date=issue_date
                ))
                
        return certs

    def _parse_languages(self, profile: Dict[str, Any]) -> List[Language]:
        languages = []
        lang_entities = self.entities_by_type.get("com.linkedin.voyager.dash.identity.profile.Language", [])
        
        for lang in lang_entities:
            name = lang.get("name")
            proficiency = lang.get("proficiency")
            
            if name:
                languages.append(Language(
                    name=name,
                    proficiency=proficiency
                ))
                
        return languages

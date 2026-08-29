from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

from app.models.profile import (
    Certification, Education, Experience, Honor, Language,
    ProfileInfo, ProfileResponse, Project, Skill, Volunteer,
)


def _type_name(entity: Dict[str, Any]) -> str:
    return str(entity.get("$type", "")).split(".")[-1]


class LinkedInParser:
    """Turns LinkedIn's normalized ``{data, included}`` Voyager graph into the
    public response schema. Every entity is indexed by URN so references
    (a position's company, a profile's geo/industry, …) can be resolved."""

    def __init__(self, raw_data: Dict[str, Any]):
        self.raw_data = raw_data or {}
        self.by_urn: Dict[str, Dict[str, Any]] = {}
        self.by_type: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self.root_urn: Optional[str] = None
        self._build_graph()

    def _build_graph(self):
        for item in self.raw_data.get("included") or []:
            urn = item.get("entityUrn")
            if urn:
                self.by_urn[urn] = item
            t = item.get("$type")
            if t:
                self.by_type[t.split(".")[-1]].append(item)

        elements = (self.raw_data.get("data") or {}).get("*elements") or []
        if elements:
            self.root_urn = elements[0]

    # ------------------------------------------------------------- helpers
    def _get(self, urn: Optional[str]) -> Dict[str, Any]:
        if not urn:
            return {}
        return self.by_urn.get(urn) or {}

    def _entities(self, type_suffix: str) -> List[Dict[str, Any]]:
        return self.by_type.get(type_suffix, [])

    @staticmethod
    def _fmt_date(d: Optional[Dict[str, Any]]) -> Optional[str]:
        if not isinstance(d, dict):
            return None
        year, month = d.get("year"), d.get("month")
        if year and month:
            return f"{year}-{int(month):02d}"
        if year:
            return str(year)
        return None

    def _date_range(self, obj: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
        dr = obj.get("dateRange") or {}
        return self._fmt_date(dr.get("start")), self._fmt_date(dr.get("end"))

    @staticmethod
    def _image(obj: Optional[Dict[str, Any]]) -> Optional[str]:
        if not isinstance(obj, dict):
            return None
        vector = obj.get("vectorImage") or (obj.get("displayImageReference") or {}).get("vectorImage")
        if not isinstance(vector, dict):
            return None
        root = vector.get("rootUrl")
        artifacts = vector.get("artifacts") or []
        if not root or not artifacts:
            return None
        best = max(artifacts, key=lambda a: a.get("width", 0))
        seg = best.get("fileIdentifyingUrlPathSegment", "")
        return f"{root}{seg}" if seg else None

    # ------------------------------------------------------------- root
    def _root_profile(self) -> Dict[str, Any]:
        root = self._get(self.root_urn)
        if root and _type_name(root) == "Profile":
            return root
        candidates = self._entities("Profile")
        if not candidates:
            raise ValueError("Invalid LinkedIn response format: no profile entity")
        return max(candidates, key=len)

    def parse(self) -> ProfileResponse:
        profile = self._root_profile()
        return ProfileResponse(
            profile=self._parse_basic_info(profile),
            experience=self._parse_experience(),
            education=self._parse_education(),
            skills=self._parse_skills(),
            certifications=self._parse_certifications(),
            languages=self._parse_languages(),
            projects=self._parse_projects(),
            honors=self._parse_honors(),
            volunteer=self._parse_volunteer(),
        )

    # ------------------------------------------------------------- sections
    def _parse_basic_info(self, p: Dict[str, Any]) -> ProfileInfo:
        first, last = p.get("firstName") or "", p.get("lastName") or ""
        name = f"{first} {last}".strip() or None

        location = p.get("locationName")
        country = None
        geo = self._get((p.get("geoLocation") or {}).get("*geo"))
        if geo:
            location = location or geo.get("defaultLocalizedName")
            country = self._get(geo.get("*country")).get("defaultLocalizedName")
        if not country:
            country = (p.get("location") or {}).get("countryCode")

        industry = self._get(p.get("industryUrn") or p.get("*industry")).get("name")

        public_id = p.get("publicIdentifier")
        member_urn = p.get("objectUrn") or ""
        member_id = member_urn.split(":")[-1] if member_urn.startswith("urn:li:member:") else None

        return ProfileInfo(
            name=name,
            first_name=first or None,
            last_name=last or None,
            headline=p.get("headline"),
            location=location,
            country=country,
            industry=industry,
            about=p.get("summary"),
            public_identifier=public_id,
            profile_url=f"https://www.linkedin.com/in/{public_id}" if public_id else None,
            member_id=member_id,
            is_premium=bool(p.get("premium")),
            is_influencer=bool(p.get("influencer")),
            profile_image=self._image(p.get("profilePicture")),
            background_image=self._image(p.get("backgroundPicture")),
        )

    def _company_bits(self, urn: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
        c = self._get(urn)
        return c.get("url"), self._image(c.get("logo"))

    def _parse_experience(self) -> List[Experience]:
        out, seen = [], set()
        for pos in self._entities("Position"):
            key = pos.get("entityUrn")
            if key and key in seen:
                continue
            seen.add(key)
            start, end = self._date_range(pos)
            url, logo = self._company_bits(pos.get("companyUrn") or pos.get("*company"))
            emp = self._get(pos.get("employmentTypeUrn") or pos.get("*employmentType")).get("name")
            out.append(Experience(
                company=pos.get("companyName"),
                company_url=url,
                company_logo=logo,
                title=pos.get("title"),
                employment_type=emp,
                location=pos.get("locationName") or pos.get("geoLocationName"),
                description=pos.get("description"),
                start_date=start,
                end_date=end,
                current=start is not None and end is None,
            ))
        out.sort(key=lambda e: (e.current, e.start_date or ""), reverse=True)
        return out

    def _parse_education(self) -> List[Education]:
        out, seen = [], set()
        for edu in self._entities("Education"):
            key = edu.get("entityUrn")
            if key and key in seen:
                continue
            seen.add(key)
            start, end = self._date_range(edu)
            school = self._get(edu.get("*school") or edu.get("schoolUrn"))
            company = self._get(edu.get("*company") or edu.get("companyUrn"))
            out.append(Education(
                institution=edu.get("schoolName") or school.get("name") or company.get("name"),
                institution_url=company.get("url") or school.get("url"),
                institution_logo=self._image(school.get("logo")) or self._image(company.get("logo")),
                degree=edu.get("degreeName"),
                field_of_study=edu.get("fieldOfStudy"),
                description=edu.get("description"),
                activities=edu.get("activities"),
                grade=edu.get("grade"),
                start_date=start,
                end_date=end,
            ))
        out.sort(key=lambda e: (e.start_date or ""), reverse=True)
        return out

    def _parse_skills(self) -> List[Skill]:
        out, seen = [], set()
        for s in self._entities("Skill"):
            name = s.get("name")
            if name and name not in seen:
                seen.add(name)
                out.append(Skill(name=name))
        return out

    def _parse_certifications(self) -> List[Certification]:
        out, seen = [], set()
        for c in self._entities("Certification"):
            name = c.get("name")
            if not name or name in seen:
                continue
            seen.add(name)
            issue, expiry = self._date_range(c)
            out.append(Certification(
                name=name,
                issuer=c.get("authority"),
                license_number=c.get("licenseNumber"),
                url=c.get("url"),
                issue_date=issue,
                expiry_date=expiry,
            ))
        return out

    def _parse_languages(self) -> List[Language]:
        out, seen = [], set()
        for lang in self._entities("Language"):
            name = lang.get("name")
            if name and name not in seen:
                seen.add(name)
                out.append(Language(name=name, proficiency=lang.get("proficiency")))
        return out

    def _parse_projects(self) -> List[Project]:
        out, seen = [], set()
        for pr in self._entities("Project"):
            title = pr.get("title")
            if not title or title in seen:
                continue
            seen.add(title)
            start, end = self._date_range(pr)
            out.append(Project(
                title=title,
                description=pr.get("description"),
                start_date=start,
                end_date=end,
            ))
        return out

    def _parse_honors(self) -> List[Honor]:
        out, seen = [], set()
        for h in self._entities("Honor"):
            title = h.get("title")
            if not title or title in seen:
                continue
            seen.add(title)
            out.append(Honor(
                title=title,
                issuer=h.get("issuer"),
                description=h.get("description"),
                date=self._fmt_date(h.get("issueDate") or h.get("issuedOn")),
            ))
        return out

    def _parse_volunteer(self) -> List[Volunteer]:
        out, seen = [], set()
        for v in self._entities("VolunteerExperience"):
            key = v.get("entityUrn")
            if key and key in seen:
                continue
            seen.add(key)
            start, end = self._date_range(v)
            out.append(Volunteer(
                organization=v.get("companyName"),
                role=v.get("role"),
                cause=v.get("cause"),
                description=v.get("description"),
                start_date=start,
                end_date=end,
            ))
        return out

import pytest

from app.linkedin.parser import LinkedInParser

ROOT = "urn:li:fsd_profile:12345"


def _profile(**extra):
    return {
        "entityUrn": ROOT,
        "firstName": "John",
        "lastName": "Doe",
        "$type": "com.linkedin.voyager.dash.identity.profile.Profile",
        **extra,
    }


def test_parser_basic_info_resolves_geo_industry_and_image():
    mock_data = {
        "data": {"*elements": [ROOT]},
        "included": [
            _profile(
                headline="Software Engineer",
                summary="I build things.",
                publicIdentifier="john-doe",
                objectUrn="urn:li:member:555",
                premium=True,
                geoLocation={"*geo": "urn:li:fsd_geo:1"},
                industryUrn="urn:li:fsd_industry:4",
                profilePicture={
                    "displayImageReference": {
                        "vectorImage": {
                            "rootUrl": "https://cdn/pic/",
                            "artifacts": [
                                {"width": 100, "fileIdentifyingUrlPathSegment": "100.jpg"},
                                {"width": 400, "fileIdentifyingUrlPathSegment": "400.jpg"},
                            ],
                        }
                    }
                },
            ),
            {"$type": "com.linkedin.voyager.dash.common.Geo", "entityUrn": "urn:li:fsd_geo:1",
             "defaultLocalizedName": "San Francisco Bay Area", "*country": "urn:li:fsd_geo:2"},
            {"$type": "com.linkedin.voyager.dash.common.Geo", "entityUrn": "urn:li:fsd_geo:2",
             "defaultLocalizedName": "United States"},
            {"$type": "com.linkedin.voyager.dash.common.Industry", "entityUrn": "urn:li:fsd_industry:4",
             "name": "Software Development"},
        ],
    }
    p = LinkedInParser(mock_data).parse().profile
    assert p.name == "John Doe"
    assert p.location == "San Francisco Bay Area"
    assert p.country == "United States"
    assert p.industry == "Software Development"
    assert p.about == "I build things."
    assert p.is_premium is True
    assert p.member_id == "555"
    assert p.profile_image == "https://cdn/pic/400.jpg"
    assert p.profile_url == "https://www.linkedin.com/in/john-doe"


def test_parser_experience_company_and_employment_type():
    mock_data = {
        "data": {"*elements": [ROOT]},
        "included": [
            _profile(),
            {
                "$type": "com.linkedin.voyager.dash.identity.profile.Position",
                "entityUrn": "urn:li:fsd_profilePosition:999",
                "companyName": "Tech Corp",
                "title": "Senior Engineer",
                "companyUrn": "urn:li:fsd_company:1",
                "employmentTypeUrn": "urn:li:fsd_employmentType:6",
                "dateRange": {"start": {"year": 2020, "month": 1}, "end": {"year": 2023, "month": 5}},
            },
            {
                "$type": "com.linkedin.voyager.dash.identity.profile.Position",
                "entityUrn": "urn:li:fsd_profilePosition:888",
                "companyName": "Startup Inc",
                "title": "Engineer",
                "dateRange": {"start": {"year": 2023, "month": 6}},
            },
            {"$type": "com.linkedin.voyager.dash.organization.Company", "entityUrn": "urn:li:fsd_company:1",
             "name": "Tech Corp", "url": "https://www.linkedin.com/company/tech-corp/"},
            {"$type": "com.linkedin.voyager.dash.identity.profile.EmploymentType",
             "entityUrn": "urn:li:fsd_employmentType:6", "name": "Internship"},
        ],
    }
    exp = LinkedInParser(mock_data).parse().experience
    assert len(exp) == 2
    # current role sorts first
    assert exp[0].company == "Startup Inc"
    assert exp[0].current is True

    tech = next(e for e in exp if e.company == "Tech Corp")
    assert tech.start_date == "2020-01"
    assert tech.end_date == "2023-05"
    assert tech.current is False
    assert tech.company_url == "https://www.linkedin.com/company/tech-corp/"
    assert tech.employment_type == "Internship"


def test_parser_sections():
    mock_data = {
        "data": {"*elements": [ROOT]},
        "included": [
            _profile(),
            {"$type": "com.linkedin.voyager.dash.identity.profile.Skill", "name": "Go"},
            {"$type": "com.linkedin.voyager.dash.identity.profile.Skill", "name": "Go"},  # dupe
            {"$type": "com.linkedin.voyager.dash.identity.profile.Skill", "name": "Python"},
            {"$type": "com.linkedin.voyager.dash.identity.profile.Language",
             "name": "English", "proficiency": "NATIVE_OR_BILINGUAL"},
            {"$type": "com.linkedin.voyager.dash.identity.profile.Certification",
             "name": "AWS SAA", "authority": "Amazon", "url": "https://x", "licenseNumber": "ABC",
             "dateRange": {"start": {"year": 2022, "month": 6}}},
            {"$type": "com.linkedin.voyager.dash.identity.profile.Project",
             "title": "Sideproject", "description": "a thing"},
        ],
    }
    r = LinkedInParser(mock_data).parse()
    assert [s.name for s in r.skills] == ["Go", "Python"]
    assert r.languages[0].proficiency == "NATIVE_OR_BILINGUAL"
    assert r.certifications[0].license_number == "ABC"
    assert r.certifications[0].issue_date == "2022-06"
    assert r.projects[0].title == "Sideproject"


def test_parser_missing_root():
    with pytest.raises(ValueError):
        LinkedInParser({"data": {}, "included": []}).parse()

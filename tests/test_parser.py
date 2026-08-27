from app.linkedin.parser import LinkedInParser

def test_parser_basic_info():
    mock_data = {
        "data": {
            "*elements": ["urn:li:fsd_profile:12345"]
        },
        "included": [
            {
                "entityUrn": "urn:li:fsd_profile:12345",
                "firstName": "John",
                "lastName": "Doe",
                "headline": "Software Engineer",
                "locationName": "San Francisco, CA",
                "summary": "I build things.",
                "publicIdentifier": "john-doe",
                "$type": "com.linkedin.voyager.dash.identity.profile.Profile"
            }
        ]
    }
    
    parser = LinkedInParser(mock_data)
    result = parser.parse()
    
    assert result.profile.name == "John Doe"
    assert result.profile.headline == "Software Engineer"
    assert result.profile.location == "San Francisco, CA"
    assert result.profile.about == "I build things."
    assert result.profile.profile_url == "https://www.linkedin.com/in/john-doe"

def test_parser_experience():
    mock_data = {
        "data": {
            "*elements": ["urn:li:fsd_profile:12345"]
        },
        "included": [
            {
                "entityUrn": "urn:li:fsd_profile:12345",
                "firstName": "John",
                "lastName": "Doe",
                "$type": "com.linkedin.voyager.dash.identity.profile.Profile"
            },
            {
                "entityUrn": "urn:li:fsd_profilePosition:999",
                "companyName": "Tech Corp",
                "title": "Senior Engineer",
                "description": "Led the backend team.",
                "locationName": "Remote",
                "dateRange": {
                    "start": {"year": 2020, "month": 1},
                    "end": {"year": 2023, "month": 5}
                },
                "$type": "com.linkedin.voyager.dash.identity.profile.Position"
            },
            {
                "entityUrn": "urn:li:fsd_profilePosition:888",
                "companyName": "Startup Inc",
                "title": "Engineer",
                "dateRange": {
                    "start": {"year": 2023, "month": 6}
                },
                "$type": "com.linkedin.voyager.dash.identity.profile.Position"
            }
        ]
    }
    
    parser = LinkedInParser(mock_data)
    result = parser.parse()
    
    assert len(result.experience) == 2
    
    # Order might depend on parser iteration (currently dictionary values order)
    # Let's just find them by companyName
    tech_corp = next(e for e in result.experience if e.company == "Tech Corp")
    assert tech_corp.title == "Senior Engineer"
    assert tech_corp.start_date == "2020-01"
    assert tech_corp.end_date == "2023-05"
    assert tech_corp.current == False
    
    startup = next(e for e in result.experience if e.company == "Startup Inc")
    assert startup.current == True
    assert startup.end_date == None

def test_parser_missing_root():
    mock_data = {
        "data": {},
        "included": []
    }
    
    try:
        parser = LinkedInParser(mock_data)
        parser.parse()
        assert False, "Should have raised ValueError"
    except ValueError:
        pass

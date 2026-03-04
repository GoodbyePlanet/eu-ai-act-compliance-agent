from frontend.sidebar import _build_about_eu_ai_act_url, _format_assessment_created_at


def test_build_about_url_uses_relative_path_for_internal_backend_hostname():
    """Internal Docker API host should resolve to a same-host relative URL."""
    result = _build_about_eu_ai_act_url("http://backend:8000")

    assert result == "/about-eu-ai-act"


def test_build_about_url_uses_api_url_for_localhost():
    """Localhost API URL should produce an absolute localhost about-page URL."""
    result = _build_about_eu_ai_act_url("http://localhost:8000")

    assert result == "http://localhost:8000/about-eu-ai-act"


def test_build_about_url_uses_api_url_for_public_domain():
    """Public API URL should produce an absolute domain about-page URL."""
    result = _build_about_eu_ai_act_url("https://eu-ai-audit.com")

    assert result == "https://eu-ai-audit.com/about-eu-ai-act"


def test_build_about_url_handles_trailing_slash():
    """Trailing slash in API URL should not create double slashes."""
    result = _build_about_eu_ai_act_url("https://eu-ai-audit.com/")

    assert result == "https://eu-ai-audit.com/about-eu-ai-act"


def test_format_assessment_created_at_formats_iso_in_utc():
    """ISO UTC timestamp should be shown as fixed UTC text."""
    created_at = "2026-03-04T07:30:00+00:00"

    result = _format_assessment_created_at(created_at)

    assert result == "2026-03-04 07:30 UTC"


def test_format_assessment_created_at_returns_original_on_parse_failure():
    """Unexpected timestamp formats should be returned unchanged."""
    invalid_created_at = "not-a-timestamp"

    result = _format_assessment_created_at(invalid_created_at)

    assert result == invalid_created_at


def test_format_assessment_created_at_legacy_format_appends_utc():
    """Legacy month/day timestamps should be labeled as UTC."""
    created_at = "Mar 04, 07:30 AM"

    result = _format_assessment_created_at(created_at)

    assert result == "Mar 04, 07:30 AM UTC"

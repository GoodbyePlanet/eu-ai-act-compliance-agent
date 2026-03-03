from frontend.sidebar import _build_about_eu_ai_act_url


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

import pytest
from fastapi.testclient import TestClient
from src.main import app

def test_api_root_status():
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    assert response.headers.get("content-type", "").startswith("application/json")
    data = response.json()
    assert data == {
        "status": "online",
        "service": "Clanomy API",
        "version": "1.0.0"
    }

def test_landing_page_serves_html():
    client = TestClient(app)
    response = client.get("/landing")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    content = response.text
    assert "Clanomy" in content
    assert "support@clanomy.com" in content
    assert "Solo Pro" in content
    assert "Duo Pro" in content
    assert "Family Pro" in content
    assert "Custom & Teams" in content
    assert "Terms of Service" in content
    assert "Privacy Policy" in content
    assert "Refund & Cancellation Policy" in content
    assert "Clanomy Web Studio" in content
    assert "assets/clanomy_logo.jpg" in content
    assert "assets/dashboard_preview.jpg" in content
    assert "What is Zero-Knowledge AES-256 Privacy" in content
    assert "Self-Hosted" in content
    assert "Business Source License 1.1" in content
    assert "unlimited, lifetime use of all pre-built slash commands" in content
    assert "Is my financial data or voice recordings used to train AI models" in content
    assert "Zero AI Training Policy" in content
    assert "https://ko-fi.com/crespoantonio" in content
    assert 'data-i18n="self.kofi_btn"' in content
    assert 'data-i18n="footer.kofi"' in content
    assert 'data-i18n="footer.kofi_link"' in content

def test_landing_page_static_assets():
    client = TestClient(app)
    
    # CSS asset
    css_resp = client.get("/styles.css")
    assert css_resp.status_code == 200
    assert "text/css" in css_resp.headers.get("content-type", "")
    assert "--accent-primary" in css_resp.text

    # JS asset
    js_resp = client.get("/script.js")
    assert js_resp.status_code == 200
    assert "javascript" in js_resp.headers.get("content-type", "")
    assert "billing-toggle" in js_resp.text
    assert "duo-price" in js_resp.text

    # Translations JS asset
    trans_resp = client.get("/translations.js")
    assert trans_resp.status_code == 200
    assert "javascript" in trans_resp.headers.get("content-type", "")
    assert "TRANSLATIONS" in trans_resp.text
    assert "Características" in trans_resp.text
    assert "Bilingual Voice & Text AI" in trans_resp.text

    # Image assets
    logo_resp = client.get("/assets/clanomy_logo.jpg")
    assert logo_resp.status_code == 200

    dashboard_resp = client.get("/assets/dashboard_preview.jpg")
    assert dashboard_resp.status_code == 200

def test_landing_page_bilingual_toggle_elements():
    client = TestClient(app)
    response = client.get("/landing")
    assert response.status_code == 200
    content = response.text
    assert 'id="lang-switch"' in content
    assert 'id="lang-btn-en"' in content
    assert 'id="lang-btn-es"' in content
    assert 'translations.js' in content
    assert 'data-i18n="nav.features"' in content
    assert 'data-i18n="hero.title"' in content
    assert 'data-i18n="pricing.title"' in content

def test_all_html_data_i18n_keys_exist_in_translations():
    import re
    client = TestClient(app)
    
    html_resp = client.get("/landing")
    assert html_resp.status_code == 200
    html_content = html_resp.text

    # Extract all data-i18n attributes from the HTML
    html_keys = set(re.findall(r'data-i18n="([^"]+)"', html_content))
    assert len(html_keys) > 50, f"Expected more than 50 data-i18n keys, found {len(html_keys)}"

    # Load translations.js
    trans_resp = client.get("/translations.js")
    assert trans_resp.status_code == 200
    trans_text = trans_resp.text

    en_part = trans_text[trans_text.find('en: {'):trans_text.find('es: {')]
    es_part = trans_text[trans_text.find('es: {'):]

    en_keys = set(re.findall(r'"([a-zA-Z0-9_\.]+)":', en_part))
    es_keys = set(re.findall(r'"([a-zA-Z0-9_\.]+)":', es_part))

    # Assert every single HTML data-i18n key exists in both English and Spanish dictionaries
    missing_in_en = html_keys - en_keys
    missing_in_es = html_keys - es_keys

    assert not missing_in_en, f"HTML keys missing in translations.js EN: {missing_in_en}"
    assert not missing_in_es, f"HTML keys missing in translations.js ES: {missing_in_es}"



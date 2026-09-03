import pytest
from fastapi.testclient import TestClient
from src.main import app

def test_landing_page_root_serves_html():
    client = TestClient(app)
    response = client.get("/")
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

    # Image assets
    logo_resp = client.get("/assets/clanomy_logo.jpg")
    assert logo_resp.status_code == 200

    dashboard_resp = client.get("/assets/dashboard_preview.jpg")
    assert dashboard_resp.status_code == 200

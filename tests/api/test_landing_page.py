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
    assert "Walk-Me" in content
    assert "clanomy@walk-me.app" in content
    assert "Solo Pro" in content
    assert "Family Pro" in content
    assert "Terms of Service" in content
    assert "Privacy Policy" in content
    assert "Refund & Cancellation Policy" in content
    assert "Clanomy Web Studio" in content
    assert "assets/clanomy_logo.jpg" in content
    assert "assets/dashboard_preview.jpg" in content

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

    # Image assets
    logo_resp = client.get("/assets/clanomy_logo.jpg")
    assert logo_resp.status_code == 200

    dashboard_resp = client.get("/assets/dashboard_preview.jpg")
    assert dashboard_resp.status_code == 200

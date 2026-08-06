import io
import uuid


def test_full_document_flow(client):
    """Test registration, login, upload and retrieve."""

    # Create a unique user
    username = f"testuser_{uuid.uuid4().hex[:8]}"

    test_user = {
        "username": username,
        "email": f"{username}@example.com",
        "password": "testpass123",
        "full_name": "Integration Test User",
        "role": "staff"
    }

    # Register
    response = client.post("/register", json=test_user)
    assert response.status_code == 200, response.text

    # Login
    response = client.post(
        "/login",
        data={
            "username": test_user["username"],
            "password": test_user["password"]
        }
    )

    assert response.status_code == 200, response.text

    token = response.json()["access_token"]

    headers = {
        "Authorization": f"Bearer {token}"
    }

    # Upload document
    response = client.post(
        "/documents/upload",
        headers=headers,
        files={
            "file": (
                "integration.pdf",
                io.BytesIO(b"Integration Test"),
                "application/pdf"
            )
        },
        data={
            "city": "Nairobi",
            "country": "Kenya",
            "description": "Integration Test Document"
        }
    )

    assert response.status_code == 200, response.text

    data = response.json()

    assert "document_id" in data

    document_id = data["document_id"]

    # Retrieve document
    response = client.get(
        f"/documents/{document_id}",
        headers=headers
    )

    assert response.status_code == 200, response.text

    document = response.json()

    assert document["id"] == document_id
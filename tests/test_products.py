import io


def get_auth_headers(client, test_user):
    # Register user
    client.post("/register", json=test_user)

    # Login
    response = client.post(
        "/login",
        data={"username": test_user["username"], "password": test_user["password"]},
    )

    token = response.json()["access_token"]

    return {"Authorization": f"Bearer {token}"}


def test_list_documents(client, test_user):

    headers = get_auth_headers(client, test_user)

    response = client.get("/documents", headers=headers)

    assert response.status_code == 200


def test_upload_document(client, test_user):

    headers = get_auth_headers(client, test_user)

    file = ("test.pdf", io.BytesIO(b"Hello World"), "application/pdf")

    response = client.post(
        "/documents/upload",
        headers=headers,
        files={"file": file},
        data={"city": "Nairobi", "country": "Kenya", "description": "Testing upload"},
    )

    assert response.status_code == 200

    data = response.json()

    assert "document_id" in data
    assert data["status"] in ["uploaded", "processing", "enriched"]

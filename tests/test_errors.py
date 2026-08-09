def test_404_error(client):
    """Test accessing a non-existent endpoint."""

    response = client.get("/this-endpoint-does-not-exist")

    assert response.status_code == 404


def test_unauthorized_documents(client):
    """Documents endpoint requires authentication."""

    response = client.get("/documents")

    assert response.status_code == 401


def test_invalid_login(client):
    """Invalid login credentials."""

    response = client.post(
        "/login", data={"username": "wronguser", "password": "wrongpassword"}
    )

    assert response.status_code == 401

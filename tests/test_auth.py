from tests.conftest import client, test_user


def test_register_user(client, test_user):
    """Test user registration."""

    response = client.post("/register", json=test_user)

    assert response.status_code == 200

    data = response.json()

    assert data["username"] == test_user["username"]
    assert data["email"] == test_user["email"]

    # Password should never be returned
    assert "password" not in data


def test_login_user(client, test_user):
    """Test user login."""

    # Register the user first
    client.post("/register", json=test_user)

    # Login
    response = client.post(
        "/login",
        data={
            "username": test_user["username"],
            "password": test_user["password"]
        }
    )

    assert response.status_code == 200

    data = response.json()

    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_invalid_password(client, test_user):
    """Login should fail with the wrong password."""

    client.post("/register", json=test_user)

    response = client.post(
        "/login",
        data={
            "username": test_user["username"],
            "password": "wrongpassword"
        }
    )

    assert response.status_code == 401
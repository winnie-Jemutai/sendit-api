from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_root_performance(benchmark):
    result = benchmark(client.get, "/")

    assert result.status_code == 200
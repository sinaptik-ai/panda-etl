from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.api.v1.extract import ExtractFields
from app.database import get_db

# Test client setup
client = TestClient(app)


# Mock get_db dependency
@pytest.fixture
def mock_db():
    """Fixture to mock the database session"""
    db = MagicMock(spec=Session)
    return db


@pytest.fixture(autouse=True)
def override_get_db(mock_db):
    """Override the get_db dependency with the mock"""

    def _override_get_db():
        return mock_db

    app.dependency_overrides[get_db] = _override_get_db
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def extract_fields():
    """Fixture to provide mock ExtractFields"""
    return ExtractFields(
        assetId=1, fields=[{"key": "field1", "description": "field2", "type": "text"}]
    )


@patch("app.repositories.project_repository.get_asset")
@patch("app.repositories.project_repository.get_asset_content")
@patch("app.api.v1.extract.extract_data")
@patch("app.repositories.user_repository.get_user_api_key")
def test_extract_success(
    mock_get_user_api_key,
    mock_extract_data,
    mock_get_asset_content,
    mock_get_asset,
    extract_fields,
    mock_db,
):
    """Test successful extraction of fields"""
    mock_asset = MagicMock(id=1, project_id=1, path=None)
    mock_get_asset.return_value = mock_asset
    mock_get_user_api_key.return_value = MagicMock(key="fake_api_key")
    mock_get_asset_content.return_value = MagicMock(
        content={"content": ["Page 1 content", "Page 2 content"]}
    )
    mock_extract_data.return_value = MagicMock(
        fields={"extracted_field1": "value1", "extracted_field2": "value2"}
    )

    response = client.post("/v1/extract/1", json=extract_fields.dict())

    assert response.status_code == 200
    assert response.json() == {
        "status": "success",
        "message": "Data extracted successfully from the file.",
        "data": {"extracted_field1": "value1", "extracted_field2": "value2"},
    }

    mock_get_asset.assert_called_once_with(db=mock_db, asset_id=1)
    mock_get_user_api_key.assert_called_once_with(mock_db)
    mock_get_asset_content.assert_called_once_with(mock_db, asset_id=1)
    mock_extract_data.assert_called_once_with(
        api_token="fake_api_key",
        fields=extract_fields.dict(),
        file_path=None,
        pdf_content=None,
    )


@patch("app.repositories.project_repository.get_asset")
def test_extract_asset_permission_error( mock_get_asset, extract_fields, mock_db):
    """Test extraction with asset permission error"""
    mock_asset = MagicMock(id=1, project_id=2)
    mock_get_asset.return_value = mock_asset

    response = client.post("/v1/extract/1", json=extract_fields.dict())

    assert response.status_code == 400
    assert response.json() == {"detail": "Asset does not belong to the specified project."}

    mock_get_asset.assert_called_once_with(db=mock_db, asset_id=1)
    mock_db.commit.assert_not_called()


@patch("app.repositories.project_repository.get_asset")
@patch("app.repositories.project_repository.get_asset_content")
@patch("app.repositories.user_repository.get_user_api_key")
@patch("app.api.v1.extract.extract_data")
def test_extract_missing_content(
    mock_extract_data,
    mock_get_user_api_key,
    mock_get_asset_content,
    mock_get_asset,
    extract_fields,
    mock_db,
):
    """Test extraction with missing asset content"""
    mock_asset = MagicMock(id=1, project_id=1, path="/path/to/file.pdf")
    mock_get_asset.return_value = mock_asset
    mock_get_user_api_key.return_value = MagicMock(key="fake_api_key")
    mock_get_asset_content.return_value = None  # Simulate missing content

    response = client.post("/v1/extract/1", json=extract_fields.dict())

    assert response.status_code == 200
    assert "status" in response.json()
    assert response.json()["status"] == "success"
    assert mock_get_asset_content.called
    mock_get_asset.assert_called_once_with(db=mock_db, asset_id=1)
    mock_get_user_api_key.assert_called_once_with(mock_db)


@patch("app.repositories.project_repository.get_asset")
@patch("app.repositories.project_repository.get_asset_content")
@patch("app.api.v1.extract.extract_data")
@patch("app.repositories.user_repository.get_user_api_key")
def test_extract_exception(
    mock_get_user_api_key,
    mock_extract_data,
    mock_get_asset_content,
    mock_get_asset,
    extract_fields,
    mock_db,
):
    """Test extraction when an exception occurs"""
    mock_asset = MagicMock(id=1, project_id=1, path="/path/to/file.pdf")
    mock_get_asset.return_value = mock_asset
    mock_get_user_api_key.return_value = MagicMock(key="fake_api_key")
    mock_get_asset_content.side_effect = Exception("Unexpected error")

    response = client.post("/v1/extract/1", json=extract_fields.dict())

    assert response.status_code == 400
    assert response.json() == {
        "detail": "An error occurred while processing the file. Please try again or contact support if the issue persists."
    }

    mock_get_asset.assert_called_once_with(db=mock_db, asset_id=1)
    mock_get_user_api_key.assert_called_once_with(mock_db)
    mock_get_asset_content.assert_called_once_with(mock_db, asset_id=1)

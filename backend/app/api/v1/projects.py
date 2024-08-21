from concurrent.futures import ThreadPoolExecutor
import os
import traceback
from typing import List
from fastapi import APIRouter, File, HTTPException, Depends, UploadFile, Query
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session

from app.database import SessionLocal, get_db
from app.schemas.project import ProjectCreate
from app.repositories import project_repository
from app.config import settings
from app.models.asset import Asset
from datetime import datetime, timezone

from app.repositories import user_repository
from app.requests import extract_text_from_file
from app.logger import Logger
from app.utils import fetch_html_and_save, generate_unique_filename, is_valid_url
from app.schemas.asset import UrlAssetCreate


# Thread pool executor for background tasks
file_preprocessor = ThreadPoolExecutor(max_workers=5)

project_router = APIRouter()

logger = Logger()


@project_router.post("/", status_code=201)
def create_project(project: ProjectCreate, db: Session = Depends(get_db)):
    if not project.name.strip():
        raise HTTPException(status_code=400, detail="Project title is required")

    db_project = project_repository.create_project(db=db, project=project)
    return {
        "status": "success",
        "message": "Project created successfully",
        "data": db_project,
    }


@project_router.get("/")
def get_projects(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    try:
        projects, total_count = project_repository.get_projects(
            db=db, page=page, page_size=page_size
        )

        return {
            "status": "success",
            "message": "Projects successfully returned",
            "data": [
                {
                    "id": project.id,
                    "name": project.name,
                    "description": project.description,
                    "created_at": project.created_at.isoformat(),
                    "updated_at": project.updated_at.isoformat(),
                }
                for project in projects
            ],
            "total_count": total_count,
            "page": page,
            "page_size": page_size,
        }
    except Exception as e:
        logger.error(traceback.print_exc())
        raise HTTPException(status_code=500, detail="Unable to process request!")


@project_router.get("/{id}")
def get_project(id: int, db: Session = Depends(get_db)):
    try:
        project = project_repository.get_project(db=db, project_id=id)
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")

        return {
            "status": "success",
            "message": "Projects successfully returned",
            "data": {
                "id": project.id,
                "name": project.name,
                "description": project.description,
                "created_at": project.created_at.isoformat(),
                "updated_at": project.updated_at.isoformat(),
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(traceback.print_exc())
        raise HTTPException(status_code=500, detail="Unable to process request!")


@project_router.get("/{id}/assets")
def get_assets(
    id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    try:
        assets, total_count = project_repository.get_assets(
            db=db, project_id=id, page=page, page_size=page_size, order_by="desc"
        )
        return {
            "status": "success",
            "message": "Projects successfully returned",
            "data": [
                {
                    "id": asset.id,
                    "filename": asset.filename,
                    "created_at": asset.created_at.isoformat(),
                    "updated_at": asset.updated_at.isoformat(),
                    "type": asset.type,
                    "details": asset.details,
                }
                for asset in assets
            ],
            "total_count": total_count,
            "page": page,
            "page_size": page_size,
        }
    except Exception as e:
        logger.error(traceback.print_exc())
        raise HTTPException(status_code=500, detail="Unable to process request!")


@project_router.post("/{id}/assets")
async def upload_files(
    id: int, files: List[UploadFile] = File(...), db: Session = Depends(get_db)
):
    try:
        project = project_repository.get_project(db=db, project_id=id)
        if project is None:
            raise HTTPException(status_code=400, detail="Project not found")

        # Ensure the upload directory exists
        os.makedirs(os.path.join(settings.upload_dir, str(id)), exist_ok=True)

        file_processing_tasks = []
        for file in files:
            # Check if the uploaded file is a PDF
            if file.content_type != "application/pdf":
                raise HTTPException(
                    status_code=400, detail=f"The file {file.filename} is not a PDF"
                )

            # Generate a secure filename
            filename = file.filename.replace(" ", "_")
            filepath = os.path.join(settings.upload_dir, str(id), filename)

            # Save the uploaded file
            with open(filepath, "wb") as buffer:
                buffer.write(await file.read())

            # Save the file info in the database
            new_asset = Asset(
                filename=filename,
                path=filepath,
                project_id=id,
            )

            db.add(new_asset)

            # Store processing task to run after commit
            file_processing_tasks.append(new_asset)

        db.commit()
        # Post-commit processing
        for asset in file_processing_tasks:
            print("Starting asset id", asset.id)
            file_preprocessor.submit(preprocess_file, asset.id)

        return JSONResponse(content="Successfully uploaded the files")
    except HTTPException:
        raise
    except Exception as e:
        print(traceback.print_exc())
        raise HTTPException(status_code=500, detail="Failed to upload files")


@project_router.post("/{id}/assets/url")
async def add_url_asset(id: int, data: UrlAssetCreate, db: Session = Depends(get_db)):
    try:
        urls = data.url
        project = project_repository.get_project(db=db, project_id=id)
        if project is None:
            raise HTTPException(status_code=400, detail="Project not found")

        if not urls:
            raise HTTPException(status_code=400, detail="Invalid Url")

        for url in urls:
            if not is_valid_url(url):
                raise HTTPException(status_code=400, detail="Invalid Url")

        url_assets = []
        for url in urls:
            os.makedirs(os.path.join(settings.upload_dir, str(id)), exist_ok=True)

            # Generate a secure filename
            filename = generate_unique_filename(url)
            filepath = os.path.join(settings.upload_dir, str(id), filename)

            fetch_html_and_save(url, filepath)

            # Save the file info in the database
            new_asset = Asset(
                filename=filename,
                path=filepath,
                project_id=id,
                type="url",
                details={"url": url},
            )

            url_assets.append(new_asset)

            db.add(new_asset)

        db.commit()

        for url_asset in url_assets:
            logger.log("Starting Preprocess Asset ID:", url_asset.id)
            file_preprocessor.submit(preprocess_file, url_asset.id)

        return JSONResponse(content="Successfully uploaded the files")
    except HTTPException:
        raise
    except Exception as e:
        print(traceback.print_exc())
        raise HTTPException(status_code=500, detail="Failed to upload files")


@project_router.get("/{id}/assets/{asset_id}")
async def get_file(asset_id: int, db: Session = Depends(get_db)):
    try:
        asset = project_repository.get_asset(db, asset_id)

        if asset is None:
            raise HTTPException(
                status_code=404, detail="File not found in the database"
            )

        filepath = asset.path

        # Check if the file exists
        if not os.path.isfile(filepath):
            raise HTTPException(status_code=404, detail="File not found on server")

        # Return the file
        return FileResponse(
            filepath, media_type="application/pdf", filename=asset.filename
        )

    except HTTPException:
        raise
    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail="Failed to retrieve file")


@project_router.get("/{id}/processes")
def get_processes(id: int, db: Session = Depends(get_db)):
    try:
        project = project_repository.get_project(db=db, project_id=id)
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")

        processes = project_repository.get_processes(db=db, project_id=id)

        return {
            "status": "success",
            "message": "Processes successfully returned",
            "data": [
                {
                    "id": process.id,
                    "name": process.name,
                    "type": process.type,
                    "status": process.status,
                    "project_id": f"{process.project_id}",
                    "details": process.details,
                    "started_at": process.started_at,
                    "completed_at": process.completed_at,
                    "created_at": process.created_at,
                    "updated_at": process.updated_at,
                    "completed_step_count": step_count,
                }
                for process, step_count in processes
            ],
        }
    except HTTPException:
        raise

    except Exception as e:
        logger.error(traceback.print_exc())
        raise HTTPException(status_code=500, detail="Failed to fetch response")


@project_router.delete("/{project_id}")
async def delete_project(project_id: int, db: Session = Depends(get_db)):
    try:
        project = project_repository.get_project(db, project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        project.deleted_at = datetime.now(tz=timezone.utc)

        # Soft delete assets associated with the project
        [assets, _count] = project_repository.get_assets(db, project_id)
        for asset in assets:
            asset.deleted_at = datetime.now(tz=timezone.utc)

        # Soft delete process associated with the project
        project_repository.delete_processes_and_steps(db, project_id)

        db.commit()

        return {"message": "Project and associated assets deleted successfully"}

    except HTTPException:
        raise

    except Exception as e:
        logger.error(traceback.print_exc())
        raise HTTPException(status_code=500, detail="Failed to delete!")


@project_router.delete("/{project_id}/assets/{asset_id}")
async def delete_asset(project_id: int, asset_id: int, db: Session = Depends(get_db)):
    try:
        project = project_repository.get_project(db, project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        asset = project_repository.get_asset(db, asset_id)

        if asset is None:
            raise HTTPException(
                status_code=404, detail="File not found in the database"
            )
        asset.deleted_at = datetime.now(tz=timezone.utc)
        db.commit()
        return {"message": "Asset deleted successfully"}

    except HTTPException:
        raise

    except Exception as e:
        logger.error(traceback.print_exc())
        raise HTTPException(status_code=500, detail="Failed to retrieve file")


def preprocess_file(asset_id: int):
    db = SessionLocal()

    try:
        asset = project_repository.get_asset(db=db, asset_id=asset_id)
        api_key = user_repository.get_user_api_key(db)
        pdf_content = extract_text_from_file(api_key.key, asset.path, asset.type)
        project_repository.add_asset_content(db, asset_id, pdf_content)

    except Exception as e:
        print(e)
        logger.error(
            f"failed to preprocess asset {asset_id}: {traceback.print_exception()}"
        )

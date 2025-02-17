import os
import traceback
from typing import List
from app.processing.file_preprocessing import process_file
from fastapi import APIRouter, File, HTTPException, Depends, UploadFile, Query
from fastapi.responses import JSONResponse, FileResponse  # Add FileResponse here
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.project import ProjectCreate, ProjectUpdate
from app.repositories import project_repository
from app.config import settings
from app.models.asset import Asset
from datetime import datetime, timezone
from app.logger import Logger
from app.utils import fetch_html_and_save, generate_unique_filename, is_valid_url
from app.schemas.asset import UrlAssetCreate
from app.vectorstore.chroma import ChromaDB


project_router = APIRouter()

logger = Logger()


@project_router.post("", status_code=201)
def create_project(project: ProjectCreate, db: Session = Depends(get_db)):
    if not project.name.strip():
        raise HTTPException(
            status_code=400, detail="Project name is required and cannot be empty."
        )

    db_project = project_repository.create_project(db=db, project=project)
    return {
        "status": "success",
        "message": "Project created successfully",
        "data": db_project,
    }


@project_router.get("")
def get_projects(
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=100),
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
                    "asset_count": asset_count,
                }
                for project, asset_count in projects
            ],
            "total_count": total_count,
            "page": page,
            "page_size": page_size,
        }
    except Exception:
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail="An internal server error occurred while processing your request. Please try again later.",
        )


@project_router.get("/{id}")
def get_project(id: int, db: Session = Depends(get_db)):
    try:
        project = project_repository.get_project(db=db, project_id=id)
        if project is None:
            raise HTTPException(
                status_code=404, detail="The requested project could not be found."
            )

        return {
            "status": "success",
            "message": "Project successfully returned",
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
    except Exception:
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail="An internal server error occurred while retrieving the project. Please try again later.",
        )


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
            "message": "Assets successfully returned",
            "data": [
                {
                    "id": asset.id,
                    "filename": asset.filename,
                    "created_at": asset.created_at.isoformat(),
                    "updated_at": asset.updated_at.isoformat(),
                    "type": asset.type,
                    "details": asset.details,
                    "size": asset.size,
                }
                for asset in assets
            ],
            "total_count": total_count,
            "page": page,
            "page_size": page_size,
        }
    except Exception:
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail="An internal server error occurred while retrieving assets. Please try again later.",
        )


@project_router.post("/{id}/assets")
async def upload_files(
    id: int, files: List[UploadFile] = File(...), db: Session = Depends(get_db)
):
    try:
        project = project_repository.get_project(db=db, project_id=id)
        if project is None:
            raise HTTPException(
                status_code=404, detail="The specified project could not be found."
            )

        # Ensure the upload directory exists
        os.makedirs(os.path.join(settings.upload_dir, str(id)), exist_ok=True)

        file_processing_tasks = []
        for file in files:
            # Check if the uploaded file is a PDF
            if file.content_type != "application/pdf":
                raise HTTPException(
                    status_code=400,
                    detail=f"The file '{file.filename}' is not a valid PDF. Please upload only PDF files.",
                )

            # Check if the file size is greater than 20MB
            if file.size > settings.max_file_size:
                raise HTTPException(
                    status_code=400,
                    detail=f"The file '{file.filename}' exceeds the maximum allowed size of 20MB. Please upload a smaller file.",
                )

            # Generate a secure filename
            filename = file.filename.replace(" ", "_")
            filepath = os.path.join(settings.upload_dir, str(id), filename)

            # Save the uploaded file
            with open(filepath, "wb") as buffer:
                buffer.write(await file.read())

            file_size = os.path.getsize(filepath)

            # Save the file info in the database
            new_asset = Asset(
                filename=filename, path=filepath, project_id=id, size=file_size
            )

            db.add(new_asset)

            # Store processing task to run after commit
            file_processing_tasks.append(new_asset)

        db.commit()

        # Add missing Asset Content
        assets = project_repository.get_assets_without_content(db=db, project_id=id)
        for asset in assets:
            project_repository.add_asset_content(db, asset.id, None)
            process_file(asset.id)

        return JSONResponse(content="Successfully uploaded the files")
    except HTTPException:
        raise
    except Exception:
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail="An error occurred while uploading files. Please try again later.",
        )


@project_router.post("/{id}/assets/url")
async def add_url_asset(id: int, data: UrlAssetCreate, db: Session = Depends(get_db)):
    try:
        urls = data.url
        project = project_repository.get_project(db=db, project_id=id)
        if project is None:
            raise HTTPException(
                status_code=404, detail="The specified project could not be found."
            )

        if not urls:
            raise HTTPException(
                status_code=400,
                detail="No URLs provided. Please provide at least one valid URL.",
            )

        for url in urls:
            if not is_valid_url(url):
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid URL format: {url}. Please provide a valid URL.",
                )

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

        # Add missing Asset Content
        assets = project_repository.get_assets_without_content(db=db, project_id=id)
        for asset in assets:
            project_repository.add_asset_content(db, asset.id, None)
            process_file(asset.id)

        return JSONResponse(content="Successfully uploaded the files")
    except HTTPException:
        raise
    except Exception:
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail="An error occurred while processing the URL asset. Please try again later.",
        )


@project_router.get("/{id}/assets/{asset_id}")
async def get_file(asset_id: int, db: Session = Depends(get_db)):
    try:
        asset = project_repository.get_asset(db, asset_id)

        if asset is None:
            raise HTTPException(
                status_code=404,
                detail="The requested file could not be found in the database.",
            )

        filepath = asset.path

        # Check if the file exists
        if not os.path.isfile(filepath):
            raise HTTPException(
                status_code=404,
                detail="The requested file could not be found on the server.",
            )

        # Return the file
        return FileResponse(
            filepath, media_type="application/pdf", filename=asset.filename
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving file: {str(e)}\n{traceback.format_exc()}")
        raise HTTPException(
            status_code=500,
            detail="An error occurred while retrieving the file. Please try again later.",
        )


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

    except Exception:
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail="Failed to fetch response")


@project_router.put("/{id}")
def update_project(id: int, project: ProjectUpdate, db: Session = Depends(get_db)):
    try:
        db_project = project_repository.get_project(db=db, project_id=id)
        if db_project is None:
            raise HTTPException(
                status_code=404, detail="The specified project could not be found."
            )
        updated_project = project_repository.update_project(
            db=db, project_id=id, project=project
        )
        return {
            "status": "success",
            "message": "Project updated successfully",
            "data": updated_project,
        }
    except HTTPException:
        raise
    except Exception:
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail="An error occurred while updating the project. Please try again later.",
        )


@project_router.delete("/{project_id}")
async def delete_project(project_id: int, db: Session = Depends(get_db)):
    try:
        project = project_repository.get_project(db, project_id)
        if not project:
            raise HTTPException(
                status_code=404, detail="The specified project could not be found."
            )

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

    except Exception:
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail="An error occurred while deleting the project. Please try again later.",
        )


@project_router.delete("/{project_id}/assets/{asset_id}")
async def delete_asset(project_id: int, asset_id: int, db: Session = Depends(get_db)):
    try:
        project = project_repository.get_project(db, project_id)
        if not project:
            raise HTTPException(
                status_code=404, detail="The specified project could not be found."
            )

        asset = project_repository.get_asset(db, asset_id)
        if asset is None:
            raise HTTPException(
                status_code=404,
                detail="The specified asset could not be found in the database.",
            )

        if asset.project_id != project_id:
            raise HTTPException(
                status_code=400,
                detail="The specified asset does not belong to the given project.",
            )

        # Store asset information before deletion
        asset_info = {
            "id": asset.id,
            "filename": asset.filename,
            "project_id": asset.project_id,
        }

        try:
            vectorstore = ChromaDB(f"panda-etl-{asset.project_id}")
            vectorstore.delete_docs(where={"asset_id": str(asset.id)})
        except Exception as vec_error:
            logger.error(f"Error deleting from vectorstore: {str(vec_error)}")
            # Continue with the asset deletion even if vectorstore deletion fails

        # Soft delete the asset
        asset.deleted_at = datetime.now(tz=timezone.utc)
        db.commit()

        logger.log(
            "info",
            f"Asset {asset_info['id']} successfully marked as deleted in the database",
        )
        return {"message": "Asset deleted successfully"}

    except HTTPException as http_error:
        raise http_error

    except Exception as e:
        db.rollback()
        error_msg = f"An error occurred while deleting the asset: {str(e)}"
        logger.error(f"{error_msg}\n{traceback.format_exc()}")
        raise HTTPException(
            status_code=500,
            detail="An error occurred while deleting the asset. Please try again later.",
        )

from app import models
from app.processing.process_queue import submit_process
from app.repositories import process_repository, project_repository, user_repository
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from .database import SessionLocal
from fastapi.middleware.cors import CORSMiddleware
from app.processing.file_preprocessing import process_file
from .config import settings
from .api import v1_router
from app.schemas.user import APIKeyRequest

# Initialize the FastAPI app
app = FastAPI()

def startup_file_preprocessing():
    try:
        with SessionLocal() as db:
            count = db.query(models.AssetContent).count()

            # Check for db initialization
            if count == 0:
                return

            projects = project_repository.get_all_projects(db)
            for project in projects:
                assets = project_repository.get_assets_without_content(
                    db=db, project_id=project.id
                )
                for asset in assets:
                    project_repository.add_asset_content(db, asset.id, None)

                asset_contents = project_repository.get_assets_content_incomplete(
                    db, project_id=project.id
                )

                for asset_content in asset_contents:
                    process_file(asset_content.id)

    except Exception as e:
        print(f"Error in startup_file_preprocessing: {e}")


def startup_pending_processes():
    try:
        with SessionLocal() as db:
            count = db.query(models.Process).count()

            if count == 0:
                return

            processes = process_repository.get_all_pending_processes(db)

            for process in processes:
                submit_process(process.id)

    except Exception as e:
        print(f"Error in startup_pending_processes: {e}")


def setup_user():
    try:
        with SessionLocal() as db:

            if settings.pandaetl_api_key:
                user = user_repository.get_users(db, n=1)
                api_key = user_repository.get_user_api_key(db)

                if not user:
                    user = user_repository.create_user(db, APIKeyRequest(email="test@pandai-etl.ai"))

                if not api_key:
                    user_repository.add_user_api_key(db, user.id, settings.pandaetl_api_key)

                print("Successfully set up user from api key")

    except Exception as e:
        print(f"Error in setup user from api key: {e}")


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins (for development)
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods
    allow_headers=["*"],  # Allow all headers
)

app.mount("/assets", StaticFiles(directory=settings.upload_dir), name="assets")

app.include_router(v1_router, prefix="/v1")

setup_user()
startup_pending_processes()
startup_file_preprocessing()

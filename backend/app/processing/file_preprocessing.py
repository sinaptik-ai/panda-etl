from concurrent.futures import ThreadPoolExecutor
from app.requests.schemas import TextExtractionResponse
from sqlalchemy.orm.exc import ObjectDeletedError
from app.models.asset_content import AssetProcessingStatus
from app.database import SessionLocal
from app.repositories import project_repository
from app.repositories import user_repository
from app.requests import extract_text_from_file
from app.logger import Logger
from app.config import settings

from app.vectorstore.chroma import ChromaDB


# Thread pool executor for background tasks
file_preprocessor = ThreadPoolExecutor(max_workers=5)
file_segmentation_executor = ThreadPoolExecutor(max_workers=1)

logger = Logger()


def process_file(asset_id: int):
    file_preprocessor.submit(preprocess_file, asset_id)


def process_segmentation(project_id: int, asset_id: int, asset_file_name: str):
    try:
        with SessionLocal() as db:
            asset_content = project_repository.get_asset_content(db, asset_id)

        vectorstore = ChromaDB(f"panda-etl-{project_id}")

        docs = []
        metadatas = []
        for content in asset_content.content["content"]:
            docs.append(content["text"])
            metadatas.append({
                    "asset_id": asset_id,
                    "filename": asset_file_name,
                    "project_id": project_id,
                    **(content["metadata"] if content.get("metadata") else {"page_number": 1}),  # Unpack all metadata or default to page_number: 1
                })

        vectorstore.add_docs(
            docs=docs,
            metadatas=metadatas,
            batch_size=settings.chroma_batch_size
        )

        project_repository.update_asset_content_status(
            db,
            asset_id=asset_id,
            status=AssetProcessingStatus.COMPLETED,
        )

    except Exception as e:
        logger.error(f"Error during segmentation for asset {asset_id}: {e}")
        with SessionLocal() as db:
            project_repository.update_asset_content_status(
                db,
                asset_id=asset_id,
                status=AssetProcessingStatus.FAILED,
            )


def preprocess_file(asset_id: int):
    try:
        # Get asset details from the database first
        with SessionLocal() as db:
            asset = project_repository.get_asset(db=db, asset_id=asset_id)

            if asset is None:
                logger.error(f"Asset with id {asset_id} not found in the database")
                return

            api_key = user_repository.get_user_api_key(db)
            api_key = api_key.key

            asset_content = project_repository.update_or_add_asset_content(
                db, asset_id, None
            )

            # Refresh the asset object
            db.refresh(asset)

        # Perform text extraction
        retries = 0
        success = False
        pdf_content = None

        while retries < settings.max_retries and not success:
            try:
                # Perform the expensive operation here, without holding the DB connection
                pdf_content: TextExtractionResponse = extract_text_from_file(api_key, asset.path)

                success = True

            except ObjectDeletedError:
                logger.error(f"Asset with id {asset_id} was deleted during processing")
                return

            except Exception as e:
                logger.error(f"Error during retry {retries} for asset {asset_id}: {e}")
                retries += 1
                if retries == settings.max_retries:
                    # Update failure status in the database
                    with SessionLocal() as db:
                        project_repository.update_asset_content_status(
                            db, asset_id=asset_id, status=AssetProcessingStatus.FAILED
                        )
                    return

        # After extraction, store the extracted content in the database
        if success and pdf_content:
            with SessionLocal() as db:
                asset_content = project_repository.update_or_add_asset_content(
                    db, asset_id, pdf_content.model_dump()
                )
                # Submit the segmentation task once the content is saved
                file_segmentation_executor.submit(
                    process_segmentation,
                    asset.project_id,
                    asset_content.asset_id,
                    asset.filename,
                )

    except Exception as e:
        # Update failure status in the database if an exception occurs
        with SessionLocal() as db:
            project_repository.update_asset_content_status(
                db, asset_id=asset_id, status=AssetProcessingStatus.FAILED
            )
        logger.error(f"Failed to preprocess asset {asset_id}: {e}")

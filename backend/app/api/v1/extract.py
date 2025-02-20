from typing import List
from app.exceptions import CreditLimitExceededException
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.repositories import project_repository
from app.repositories import user_repository
from app.requests import extract_data, extract_field_descriptions
from app.logger import Logger
import traceback
from app.config import settings


extract_router = APIRouter()

logger = Logger()


class Field(BaseModel):
    key: str
    type: str
    description: str


class ExtractFields(BaseModel):
    fields: List[Field]
    assetId: int


class GetFieldDescriptionRequest(BaseModel):
    fields: List[str]


@extract_router.post("/{project_id}", status_code=200)
async def extract(
    project_id: int, fields: ExtractFields, db: Session = Depends(get_db)
):
    try:
        asset = project_repository.get_asset(db=db, asset_id=fields.assetId)

        if asset.project_id != project_id:
            raise HTTPException(
                status_code=400, detail="Asset does not belong to the specified project."
            )

        api_key = user_repository.get_user_api_key(db)

        asset_content = project_repository.get_asset_content(db, asset_id=asset.id)

        if asset_content:

            asset_content = (
                "\n".join(item["text"] for item in asset_content.content.get("content", []) if "text" in item)
                if asset_content.content
                else None
            )

        data = extract_data(
            api_token=api_key.key,
            fields=fields.dict(),
            file_path=asset.path if not asset_content else None,
            pdf_content=(None if not asset_content else asset_content),
        )

        return {
            "status": "success",
            "message": "Data extracted successfully from the file.",
            "data": data.fields,
        }

    except HTTPException:
        raise

    except Exception:
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=400, detail="An error occurred while processing the file. Please try again or contact support if the issue persists.")


@extract_router.post("/{project_id}/field-descriptions", status_code=200)
async def get_field_descriptions(
    project_id: int, fields: GetFieldDescriptionRequest, db: Session = Depends(get_db)
):
    try:
        project = project_repository.get_project(db=db, project_id=project_id)

        if not project:
            raise HTTPException(status_code=404, detail="Project not found.")

        api_key = user_repository.get_user_api_key(db)

        settings.max_retries
        retries = 0
        success = False
        while retries < settings.max_retries and not success:
            try:
                data = extract_field_descriptions(
                    api_token=api_key.key, fields=fields.fields
                )
                success = True
                return {
                    "status": "success",
                    "message": "Field descriptions generated successfully.",
                    "data": data,
                }

            except CreditLimitExceededException:
                raise HTTPException(
                    status_code=402, detail="Credit limit Reached, Wait next month or upgrade your Plan!"
                )

            except Exception as e:
                logger.error(e)
                logger.log("Retrying AI field description generation.")
                retries += 1

        raise HTTPException(
            status_code=400, detail="Unable to generate AI field descriptions. Please try again later."
        )

    except HTTPException:
        raise

    except Exception:
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail="An unexpected error occurred. Please try again or contact support if the issue persists.")

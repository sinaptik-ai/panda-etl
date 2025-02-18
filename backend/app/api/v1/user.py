from fastapi import APIRouter, Depends, HTTPException
from requests import Session
from app.database import get_db
from app.schemas.user import APIKeyRequest, UpdateAPIKeyRequest, UserUpdateRequest
from app.repositories import user_repository
from app import requests


user_router = APIRouter()


@user_router.post("/request-api-key", status_code=200)
def request_user_api_key(api_key_request: APIKeyRequest, db: Session = Depends(get_db)):

    user = user_repository.get_user(db, api_key_request.email)

    if not user:
        user = user_repository.create_user(db, api_key_request)

    message = requests.request_api_key(user.email)

    return {
        "status": "success",
        "message": message,
        "data": None,
    }


@user_router.post("/save-api-key", status_code=201)
def save_user_api_key(
    api_key_request: UpdateAPIKeyRequest, db: Session = Depends(get_db)
):

    users = user_repository.get_users(db, n=1)

    if not users:
        raise HTTPException(status_code=404, detail="No User Exists!")

    try:
        requests.get_user_usage_data(api_key_request.api_key)
    except Exception:
        raise HTTPException(
            status_code=400, detail="Invalid API Key"
        )
    user_repository.update_user_api_key(db, users[0].id, api_key_request.api_key)

    return {
        "status": "success",
        "message": "Api Key updated successfully!",
        "data": None,
    }


@user_router.get("/get-api-key", status_code=200)
def get_user_api_key(db: Session = Depends(get_db)):
    users = user_repository.get_users(db, n=1)

    if not users:
        raise HTTPException(status_code=404, detail="No User Exists!")

    api_key = user_repository.get_user_api_key(db, users[0].id)

    return {
        "status": "success",
        "message": "Api Key updated successfully!",
        "data": api_key,
    }


@user_router.get("/getme", status_code=200)
def get_me(db: Session = Depends(get_db)):
    users = user_repository.get_users(db, n=1)


    return {
        "status": "success",
        "message": "User details returned successfully!",
        "data": users[0] if len(users) > 0 else None,
    }


@user_router.put("/update-user-info")
async def update_user(user_update: UserUpdateRequest, db: Session = Depends(get_db)):
    user = user_repository.update_user(db, user_update)
    return {
        "status": "success",
        "message": "User details successfully updated!",
        "data": user,
    }


@user_router.get("/usage", status_code=200)
async def get_user_usage(db: Session = Depends(get_db)):
    try:
        users = user_repository.get_users(db, n=1)

        if not users:
            raise HTTPException(status_code=404, detail="No User Exists!")

        api_key = user_repository.get_user_api_key(db, users[0].id)

        if not api_key:
            raise HTTPException(status_code=404, detail="API Key not found!")

        usage_data = requests.get_user_usage_data(api_key.key)

        return {
            "status": "success",
            "message": "User usage data retrieved successfully!",
            "data": usage_data,
        }
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=500, detail="Failed to retrieve user usage data"
        )

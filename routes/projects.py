import datetime
from fastapi import APIRouter, HTTPException, Depends, Header, status
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from bson import ObjectId
from db import get_database
from utils.auth_helper import decode_token

router = APIRouter(prefix="/projects", tags=["projects"])


# Authentication dependency (copied from auth-service)
async def get_current_user(authorization: Optional[str] = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization credentials invalid or missing"
        )
    token = authorization.split(" ")[1]
    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token signature expired or malformed"
        )
    db = get_database()
    if db is None:
        return {"username": payload.get("sub"), "email": "fallback@archgen.ai"}
    user = await db["users"].find_one({"username": payload.get("sub")})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorized identity not found in database"
        )
    return {"id": str(user["_id"]), "username": user["username"], "email": user["email"]}


class ProjectSaveInput(BaseModel):
    id: Optional[str] = None
    name: str
    nodes: List[Dict[str, Any]]
    edges: List[Dict[str, Any]]
    services: List[Dict[str, Any]]
    cloud_provider: str
    cost_estimate: float
    region: Optional[str] = None
    workload_type: Optional[str] = None
    availability_target: Optional[str] = None
    rto: Optional[str] = None
    rpo: Optional[str] = None


@router.post("/")
async def save_project(input_data: ProjectSaveInput, current_user: dict = Depends(get_current_user)):
    db = get_database()
    if db is None:
        return {"status": "success", "message": "Mock save successful."}

    project_doc = {
        "username": current_user["username"],
        "name": input_data.name,
        "nodes": input_data.nodes,
        "edges": input_data.edges,
        "services": input_data.services,
        "cloud_provider": input_data.cloud_provider,
        "cost_estimate": input_data.cost_estimate,
        "region": input_data.region,
        "workload_type": input_data.workload_type,
        "availability_target": input_data.availability_target,
        "rto": input_data.rto,
        "rpo": input_data.rpo,
    }

    if input_data.id:
        try:
            object_id = ObjectId(input_data.id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid project identifier formatting.")

        # Load existing project to preserve/append versions
        existing = await db["projects"].find_one({"_id": object_id, "username": current_user["username"]})
        if not existing:
            raise HTTPException(status_code=404, detail="Project not found or unauthorized.")

        versions = existing.get("versions", [])

        # Create a new version snapshot
        new_version = {
            "version_id": f"v{len(versions) + 1}.0.0",
            "timestamp": datetime.datetime.utcnow().isoformat(),
            "nodes": input_data.nodes,
            "edges": input_data.edges,
            "services": input_data.services,
            "cost_estimate": input_data.cost_estimate
        }
        versions.append(new_version)
        project_doc["versions"] = versions

        result = await db["projects"].update_one(
            {"_id": object_id, "username": current_user["username"]},
            {"$set": project_doc}
        )
        return {"status": "success", "id": input_data.id, "message": "Project updated and snapshot created successfully."}
    else:
        # Create first initial snapshot
        first_version = {
            "version_id": "v1.0.0",
            "timestamp": datetime.datetime.utcnow().isoformat(),
            "nodes": input_data.nodes,
            "edges": input_data.edges,
            "services": input_data.services,
            "cost_estimate": input_data.cost_estimate
        }
        project_doc["versions"] = [first_version]
        result = await db["projects"].insert_one(project_doc)
        return {"status": "success", "id": str(result.inserted_id), "message": "Project saved successfully."}


@router.get("/")
async def list_projects(current_user: dict = Depends(get_current_user)):
    db = get_database()
    if db is None:
        return []
    cursor = db["projects"].find({"username": current_user["username"]})
    projects = []
    async for doc in cursor:
        doc["id"] = str(doc["_id"])
        del doc["_id"]
        projects.append(doc)
    return projects


@router.get("/{project_id}")
async def get_project(project_id: str, current_user: dict = Depends(get_current_user)):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=404, detail="Mock database active. Project not found.")
    try:
        project = await db["projects"].find_one({"_id": ObjectId(project_id), "username": current_user["username"]})
        if not project:
            raise HTTPException(status_code=404, detail="Project not found.")
        project["id"] = str(project["_id"])
        del project["_id"]
        return project
    except Exception:
        raise HTTPException(status_code=400, detail="Malformed project identifier.")


@router.delete("/{project_id}")
async def delete_project(project_id: str, current_user: dict = Depends(get_current_user)):
    db = get_database()
    if db is None:
        return {"status": "success", "message": "Mock delete successful."}
    try:
        result = await db["projects"].delete_one({"_id": ObjectId(project_id), "username": current_user["username"]})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Project not found or unauthorized.")
        return {"status": "success", "message": "Project deleted successfully."}
    except Exception:
        raise HTTPException(status_code=400, detail="Malformed project identifier.")


@router.get("/{project_id}/versions")
async def get_project_versions(project_id: str, current_user: dict = Depends(get_current_user)):
    db = get_database()
    if db is None:
        return []
    try:
        project = await db["projects"].find_one({"_id": ObjectId(project_id), "username": current_user["username"]})
        if not project:
            raise HTTPException(status_code=404, detail="Project not found.")
        return project.get("versions", [])
    except Exception:
        raise HTTPException(status_code=400, detail="Malformed project identifier.")


@router.post("/{project_id}/versions/{version_id}/rollback")
async def rollback_project_version(project_id: str, version_id: str, current_user: dict = Depends(get_current_user)):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=404, detail="Mock database active.")
    try:
        object_id = ObjectId(project_id)
        project = await db["projects"].find_one({"_id": object_id, "username": current_user["username"]})
        if not project:
            raise HTTPException(status_code=404, detail="Project not found.")

        versions = project.get("versions", [])
        target_version = next((v for v in versions if v.get("version_id") == version_id), None)
        if not target_version:
            raise HTTPException(status_code=404, detail=f"Version snapshot '{version_id}' not found.")

        # Restore active states
        await db["projects"].update_one(
            {"_id": object_id, "username": current_user["username"]},
            {
                "$set": {
                    "nodes": target_version["nodes"],
                    "edges": target_version["edges"],
                    "services": target_version["services"],
                    "cost_estimate": target_version["cost_estimate"]
                }
            }
        )
        return {"status": "success", "message": f"Successfully rolled back project to version {version_id}."}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Rollback failed: {str(e)}")

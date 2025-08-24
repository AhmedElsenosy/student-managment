from io import BytesIO
from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
from bson import ObjectId, errors as bson_errors
from dotenv import load_dotenv
import cv2
import numpy as np
import os
import base64
from utils.bubble_sheet_processor import process_bubble_sheet
from app.dependencies.auth import get_current_assistant

load_dotenv()

bubbles_router = APIRouter(prefix="/bubble", tags=["Bubble"])

@bubbles_router.post("/process")
async def process_bubble_sheet_endpoint(image_file: UploadFile = File(...), assistant=Depends(get_current_assistant)):
    try:
        contents = await image_file.read()
        image = cv2.imdecode(np.frombuffer(contents, np.uint8), cv2.IMREAD_COLOR)

        result = process_bubble_sheet(image)
        visualization_image = result.get("visualization_image")

        if visualization_image is None:
            return {
                "error": "No visualization image returned from processor",
                "results": result.get("results", {})  # لإبقاء نفس البنية
            }

        # Encode image to PNG and then to base64
        success, buffer = cv2.imencode(".png", visualization_image)
        if not success:
            return {"error": "Failed to encode image"}

        base64_image = base64.b64encode(buffer.tobytes()).decode("utf-8")

        # Build response
        return {
            "image_base64": base64_image,
            "results": result.get("results", {}),
        }

    except bson_errors.InvalidId as e:
        return {"error": "Invalid ObjectId format", "details": str(e)}
    except Exception as e:
        return {"error": "An error occurred while processing the bubble sheet", "details": str(e)}
import os
import sys
import asyncio
import logging

# Ensure ProactorEventLoop is used on Windows so subprocesses (Scrapy & Playwright) work
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl

import config
from scraper.models import ExtractionResult
from scraper.service import extract_contact_and_location

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("api")

app = FastAPI(
    title="Contact Details & Location Retriever",
    description="Intelligent web crawler combining Scrapy, Playwright, and OpenAI for contact and location discovery.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory history for current session
extraction_history: List[ExtractionResult] = []

class ExtractRequest(BaseModel):
    url: str
    force_playwright: bool = False

@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "openai_configured": bool(config.OPENAI_API_KEY),
        "scrapy_ready": True,
        "playwright_ready": True
    }

@app.post("/api/extract", response_model=ExtractionResult)
async def extract_url(req: ExtractRequest):
    url = req.url.strip()
    if not url:
        raise HTTPException(status_code=400, detail="Website URL cannot be empty")

    logger.info(f"Received extraction request for: {url} (Force Playwright: {req.force_playwright})")
    
    try:
        result = await extract_contact_and_location(url, force_playwright=req.force_playwright)
        # Store in session history (keep up to 50)
        extraction_history.insert(0, result)
        if len(extraction_history) > 50:
            extraction_history.pop()
        return result
    except Exception as exc:
        logger.error(f"Error processing URL {url}: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))

@app.get("/api/history", response_model=List[ExtractionResult])
async def get_history():
    return extraction_history

# Mount static files for the UI
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=config.HOST, port=config.PORT, loop="asyncio")

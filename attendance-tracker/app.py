from fastapi import FastAPI, Request
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

@app.get("/")
async def root():
	return {"service": "attendance-tracker", "status": "ready"}

@app.get("/healthz")
async def healthz():
	return {"ok": True}

@app.post("/webhook")
async def webhook(request: Request):
	data = await request.json()
	logger.info(f"Received webhook: {data}")
	# We will add logic here to process the message
	return {"status": "success"}

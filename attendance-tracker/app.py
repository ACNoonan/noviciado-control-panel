from fastapi import FastAPI, Request
from datetime import datetime, date
import logging
import sqlite3
from pathlib import Path
from contextlib import contextmanager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# Database setup
DB_PATH = Path("/app/data/attendance.db")
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

@contextmanager
def get_db():
	conn = sqlite3.connect(str(DB_PATH))
	conn.row_factory = sqlite3.Row
	try:
		yield conn
		conn.commit()
	except Exception as e:
		conn.rollback()
		raise e
	finally:
		conn.close()

def init_db():
	with get_db() as conn:
		conn.execute("""
			CREATE TABLE IF NOT EXISTS messages (
				id INTEGER PRIMARY KEY AUTOINCREMENT,
				message_id TEXT UNIQUE,
				phone_number TEXT NOT NULL,
				contact_name TEXT,
				message_body TEXT,
				timestamp DATETIME NOT NULL,
				created_at DATETIME DEFAULT CURRENT_TIMESTAMP
			)
		""")
		conn.execute("""
			CREATE TABLE IF NOT EXISTS attendance (
				id INTEGER PRIMARY KEY AUTOINCREMENT,
				phone_number TEXT NOT NULL,
				contact_name TEXT,
				date DATE NOT NULL,
				first_message_time DATETIME NOT NULL,
				created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
				UNIQUE(phone_number, date)
			)
		""")
		conn.execute("""
			CREATE INDEX IF NOT EXISTS idx_messages_phone_timestamp 
			ON messages(phone_number, timestamp)
		""")
		conn.execute("""
			CREATE INDEX IF NOT EXISTS idx_attendance_date 
			ON attendance(date)
		""")

# Initialize database on startup
init_db()

@app.get("/")
async def root():
	return {"service": "attendance-tracker", "status": "ready"}

@app.get("/healthz")
async def healthz():
	return {"ok": True}

@app.post("/webhook")
async def webhook(request: Request):
	try:
		data = await request.json()
		logger.info(f"Received webhook: {data}")
		
		# Parse WAHA webhook payload
		event = data.get("event")
		if event != "message":
			return {"status": "ignored", "reason": "not a message event"}
		
		payload = data.get("payload", {})
		
		# Skip messages from me (bot)
		if payload.get("fromMe"):
			return {"status": "ignored", "reason": "message from self"}
		
		# Extract message details
		message_id = payload.get("id")
		phone_number = payload.get("from", "").split("@")[0]  # Remove @c.us
		contact_name = payload.get("_data", {}).get("notifyName", "Unknown")
		message_body = payload.get("body", "")
		timestamp = datetime.fromtimestamp(payload.get("timestamp", 0))
		message_date = timestamp.date()
		
		if not phone_number:
			return {"status": "error", "reason": "no phone number"}
		
		with get_db() as conn:
			# Store the message
			try:
				conn.execute("""
					INSERT INTO messages (message_id, phone_number, contact_name, message_body, timestamp)
					VALUES (?, ?, ?, ?, ?)
				""", (message_id, phone_number, contact_name, message_body, timestamp))
				logger.info(f"Stored message from {contact_name} ({phone_number})")
			except sqlite3.IntegrityError:
				logger.info(f"Duplicate message {message_id}, skipping")
				return {"status": "duplicate"}
			
			# Check if this is the first message of the day
			cursor = conn.execute("""
				SELECT 1 FROM attendance 
				WHERE phone_number = ? AND date = ?
			""", (phone_number, message_date))
			
			if not cursor.fetchone():
				# First message of the day - record attendance
				conn.execute("""
					INSERT INTO attendance (phone_number, contact_name, date, first_message_time)
					VALUES (?, ?, ?, ?)
				""", (phone_number, contact_name, message_date, timestamp))
				logger.info(f"✅ Attendance recorded for {contact_name} ({phone_number}) on {message_date}")
				return {"status": "success", "attendance": True, "contact": contact_name}
			else:
				logger.info(f"Additional message from {contact_name} - attendance already recorded today")
				return {"status": "success", "attendance": False, "contact": contact_name}
	
	except Exception as e:
		logger.error(f"Error processing webhook: {e}", exc_info=True)
		return {"status": "error", "message": str(e)}

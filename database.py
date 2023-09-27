import os
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import PyMongoError, ConnectionFailure, ServerSelectionTimeoutError
from fastapi.exceptions import HTTPException

load_dotenv()

client = MongoClient(os.getenv("MONGO_URL"))
db = client[os.getenv("DB_NAME")]

users = db.users
users.create_index([("username", 1)], unique=True)
waiting_users = db.waiting_users
waiting_users.create_index([("username", 1)], unique=True)
invitations = db.invitations
games = db.games


def handle_db_exception(exception: PyMongoError):
    if isinstance(exception, ConnectionFailure) or isinstance(exception, ServerSelectionTimeoutError):
        raise HTTPException(status_code=500, detail="Could not connect to the database")
    else:
        raise HTTPException(status_code=500, detail="Database error")

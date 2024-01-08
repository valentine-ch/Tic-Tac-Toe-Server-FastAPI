import os
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import (
    PyMongoError, ConnectionFailure, OperationFailure, ConfigurationError,
    CursorNotFound, DuplicateKeyError, ExecutionTimeout, NetworkTimeout,
    ServerSelectionTimeoutError, WriteError, WriteConcernError
)
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


def handle_db_exception(error: PyMongoError):
    if isinstance(error, ConnectionFailure):
        raise HTTPException(status_code=503, detail="Database connection failure")
    elif isinstance(error, OperationFailure):
        raise HTTPException(status_code=500, detail="Database operation failed")
    elif isinstance(error, ConfigurationError):
        raise HTTPException(status_code=500, detail="Database configuration error")
    elif isinstance(error, CursorNotFound):
        raise HTTPException(status_code=404, detail="Database error: Cursor not found")
    elif isinstance(error, DuplicateKeyError):
        raise HTTPException(status_code=409, detail="Database error: Duplicate key error")
    elif isinstance(error, ExecutionTimeout):
        raise HTTPException(status_code=408, detail="Database error: Execution timeout")
    elif isinstance(error, NetworkTimeout):
        raise HTTPException(status_code=504, detail="Database error: Network timeout")
    elif isinstance(error, ServerSelectionTimeoutError):
        raise HTTPException(status_code=503, detail="Database error: Server selection timeout")
    elif isinstance(error, WriteError):
        raise HTTPException(status_code=500, detail="Database error: Write error occurred")
    elif isinstance(error, WriteConcernError):
        raise HTTPException(status_code=500, detail="Database error: Write concern failed")
    else:
        raise HTTPException(status_code=500, detail="Unknown database error")

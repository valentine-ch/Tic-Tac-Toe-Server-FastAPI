from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.security import HTTPBasic, HTTPBasicCredentials, OAuth2PasswordBearer
from argon2 import PasswordHasher
from argon2.exceptions import Argon2Error
import jwt
import secrets
import sqlite3
import re
from invitations import InvitationManager
from game import Game, GameManager
from schemas import NewMove, Invitation, InvitationResponse

app = FastAPI()
security = HTTPBasic()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
ph = PasswordHasher()
secret_key = secrets.token_hex(256)
waiting_users = set()
game_manager = GameManager()
invitation_manager = InvitationManager()


def generate_token(username):
    token = jwt.encode({'user': username}, secret_key, algorithm='HS256')
    return token


def verify_token(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, secret_key, algorithms=['HS256'])
        return payload['user']
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=400, detail="Signature has expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=400, detail="Invalid token")


def validate_username(username: str):
    if not (2 <= len(username) <= 16):
        raise HTTPException(status_code=400, detail="Username must be 2 to 16 characters long")

    if not re.match(r"^[a-zA-Z0-9]+$", username):
        raise HTTPException(status_code=400, detail="Username can have only English letters and numbers")


def validate_password(password: str):
    if not (8 <= len(password) <= 32):
        raise HTTPException(status_code=400, detail="Password must be 8 to 32 characters long")

    if not re.match(r"^[!-~]+$", password):
        raise HTTPException(status_code=400, detail="Password can have only ASCII symbols excluding whitespace")


@app.get("/check_availability")
async def check_availability():
    return {"message": "Tic-tac-toe server is available here"}


@app.post("/create_user")
async def create_user(credentials: HTTPBasicCredentials = Depends(security)):
    username = credentials.username
    password = credentials.password
    validate_username(username)
    validate_password(password)
    hashed_password = ph.hash(password)

    with sqlite3.connect("users.sqlite") as connection:
        cursor = connection.cursor()

        create_table_query = '''
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            hashed_password TEXT NOT NULL
        )
        '''
        cursor.execute(create_table_query)

        select_query = "SELECT username FROM users WHERE username = ?"
        cursor.execute(select_query, (username,))

        if cursor.fetchone():
            raise HTTPException(status_code=400, detail="This username is taken")

        insert_query = "INSERT INTO users (username, hashed_password) VALUES (?, ?)"
        cursor.execute(insert_query, (username, hashed_password))
        connection.commit()

        token = generate_token(username)

        return {"status": "User created", "token": token}


@app.post("/login")
async def login(credentials: HTTPBasicCredentials = Depends(security)):
    username = credentials.username
    password = credentials.password

    with sqlite3.connect("users.sqlite") as connection:
        cursor = connection.cursor()

        create_table_query = '''
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            hashed_password TEXT NOT NULL
        )
        '''
        cursor.execute(create_table_query)

        select_query = "SELECT hashed_password FROM users WHERE username = ?"
        cursor.execute(select_query, (username,))
        result = cursor.fetchone()

        if result is None:
            raise HTTPException(status_code=400, detail="Username does not exist")

        try:
            if ph.verify(result[0], password):
                token = generate_token(username)
                return {"status": "Logged in", "token": token}
            else:
                raise HTTPException(status_code=400, detail="Incorrect username or password")
        except Argon2Error:
            raise HTTPException(status_code=400, detail="Incorrect username or password")


@app.post("/start_waiting")
async def start_waiting(username: str = Depends(verify_token)):
    waiting_users.add(username)
    return {"status": "Waiting for game"}


@app.post("/stop_waiting")
async def stop_waiting(username: str = Depends(verify_token)):
    waiting_users.discard(username)
    return {"status": "Stopped waiting"}


@app.get("/waiting_users")
async def get_waiting_users(username: str = Depends(verify_token)):
    return {"waiting_users": list(waiting_users)}


@app.post("/invite")
async def invite_user(invitation: Invitation, inviter: str = Depends(verify_token)):
    if invitation.invited not in waiting_users:
        raise HTTPException(status_code=400, detail="Invited user is not waiting for a game")

    if invitation.invited == inviter:
        raise HTTPException(status_code=400, detail="You cannot invite yourself")

    if invitation.grid_properties.size < 3 or invitation.grid_properties.size > 26 or \
            invitation.grid_properties.winning_line > invitation.grid_properties.size:
        raise HTTPException(status_code=400, detail="Grid properties not allowed")

    invitation_id = invitation_manager.create_invitation(inviter=inviter,
                                                         invited=invitation.invited,
                                                         grid_properties=invitation.grid_properties,
                                                         inviter_playing_x=invitation.inviter_playing_x)

    return {"invitation_id": invitation_id}


@app.get("/poll_invitations")
async def poll_invitations(username: str = Depends(verify_token)):
    invitations = invitation_manager.get_invitations(username)
    return {"invitations": invitations}


@app.get("/poll_invitation_status")
async def poll_invitation_status(invitation_id: str, username: str = Depends(verify_token)):
    status = invitation_manager.get_status(invitation_id, username)
    if status == "accepted":
        return {"status": status, "game_id": invitation_manager.get_game_id(invitation_id)}
    else:
        return {"status": status}


@app.post("/respond_invitation")
async def respond_invitation(invitation_response: InvitationResponse, username: str = Depends(verify_token)):
    invitation_id = invitation_response.invitation_id
    response = invitation_response.response

    if response.lower() == "accept":
        invitation = invitation_manager.invitations.get(invitation_id)
        if invitation and invitation["invited"] == username and invitation["status"] == "pending":
            size = invitation["grid_properties"].size
            winning_line = invitation["grid_properties"].winning_line

            if invitation["inviter_playing_x"]:
                game_id = game_manager.create_game(invitation["inviter"], invitation["invited"], size, winning_line)
            else:
                game_id = game_manager.create_game(invitation["invited"], invitation["inviter"], size, winning_line)

            waiting_users.discard(invitation["inviter"])
            waiting_users.discard(invitation["invited"])

            invitation_manager.accept_invitation(invitation_id, game_id)

            return {"game_id": game_id}

        elif invitation is None:
            raise HTTPException(status_code=404, detail="Invitation not found")
        elif invitation["invited"] != username:
            raise HTTPException(status_code=403, detail="This invitation is not for you")
        elif invitation["status"] == "cancelled":
            raise HTTPException(status_code=410, detail="Invitation cancelled by inviter")
        elif invitation["status"] != "pending":
            raise HTTPException(status_code=409, detail="Invitation already responded to")

    elif response.lower() == "decline":
        invitation_manager.decline_invitation(invitation_id, username)
        return {"detail": "Invitation declined"}
    else:
        raise HTTPException(status_code=400, detail="Invalid response")


@app.post("/cancel_invitation")
async def cancel_invitation(invitation_id: str, username: str = Depends(verify_token)):
    invitation_manager.cancel_invitation(invitation_id, username)
    return {"detail": "Invitation cancelled"}


@app.post("/make_move")
async def make_move(new_move: NewMove, username: str = Depends(verify_token)):
    game_id = new_move.game_id
    cell = new_move.cell

    game = game_manager.find_game_by_id(game_id)
    if game is None:
        raise HTTPException(status_code=404, detail="Game not found")

    if username != game.x_player_name and username != game.o_player_name:
        raise HTTPException(status_code=403, detail="You are not a player in this game")

    try:
        game.make_move(username, cell)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {"game_state": game.state}


@app.get("/poll_game")
async def poll_game(game_id, username: str = Depends(verify_token)):
    game = game_manager.find_game_by_id(game_id)
    if game is None:
        raise HTTPException(status_code=404, detail="Game not found")

    if username != game.x_player_name and username != game.o_player_name:
        raise HTTPException(status_code=403, detail="You are not a player in this game")

    last_move = game.last_move

    if last_move and last_move["player_name"] != username:
        return {
            "new_move": True,
            "cell": last_move["cell"],
            "game_state": game.state
        }
    else:
        return {
            "new_move": False,
            "game_state": game.state
        }

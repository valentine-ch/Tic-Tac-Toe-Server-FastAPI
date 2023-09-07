from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.security import HTTPBasic, HTTPBasicCredentials, OAuth2PasswordBearer
from fastapi.responses import JSONResponse
from argon2 import PasswordHasher
from argon2.exceptions import Argon2Error
import jwt
import secrets
import sqlite3
import re
from invitations import InvitationManager
from game import Game, GameManager
from schemas import NewMove, Invitation, InvitationResponse, PlayAgain

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


@app.delete("/delete_account")
async def delete_account(credentials: HTTPBasicCredentials = Depends(security)):
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
            if not ph.verify(result[0], password):
                raise HTTPException(status_code=400, detail="Incorrect username or password")
        except Argon2Error:
            raise HTTPException(status_code=400, detail="Incorrect username or password")

        try:
            delete_query = "DELETE FROM users WHERE username = ?"
            cursor.execute(delete_query, (username,))
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="Failed to delete account")

        return {"status": "Account deleted"}


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
    return {"waiting_users": list(waiting_users - {username})}


@app.post("/invite")
async def invite_user(invitation: Invitation, inviter: str = Depends(verify_token)):
    if invitation.invited not in waiting_users:
        raise HTTPException(status_code=400, detail="Invited user is not waiting for a game")

    if invitation.invited == inviter:
        raise HTTPException(status_code=400, detail="You cannot invite yourself")

    if invitation.grid_properties.size < 3 or invitation.grid_properties.size > 26 or \
            invitation.grid_properties.winning_line > invitation.grid_properties.size:
        raise HTTPException(status_code=400, detail="Grid properties not allowed")

    if invitation.play_again_scheme not in {"same", "alternating", "winner_plays_x", "winner_plays_o"}:
        raise HTTPException(status_code=400, detail="Unknown play again scheme")

    invitation_id = invitation_manager.create_invitation(inviter=inviter,
                                                         invited=invitation.invited,
                                                         grid_properties=invitation.grid_properties,
                                                         inviter_playing_x=invitation.inviter_playing_x,
                                                         play_again_scheme=invitation.play_again_scheme)

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
                game_id = game_manager.create_game(invitation["inviter"], invitation["invited"],
                                                   size, winning_line, invitation["play_again_scheme"])
            else:
                game_id = game_manager.create_game(invitation["invited"], invitation["inviter"],
                                                   size, winning_line, invitation["play_again_scheme"])

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


@app.get("/get_sent_invitations")
async def get_sent_invitations(username: str = Depends(verify_token)):
    invitations = invitation_manager.get_sent_invitations(username)
    return {"sent_invitations": invitations}


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
async def poll_game(game_id: str, username: str = Depends(verify_token)):
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


@app.get("/get_ongoing_games")
async def get_ongoing_games(username: str = Depends(verify_token)):
    games = game_manager.get_ongoing_games_by_username(username)
    return {"ongoing_games": games}


@app.get("/get_full_game_state")
async def get_full_game_state(game_id: str, username: str = Depends(verify_token)):
    game = game_manager.find_game_by_id(game_id)
    if game is None:
        raise HTTPException(status_code=404, detail="Game not found")

    if username == game.x_player_name:
        user_playing_x = True
        user_turn = game.x_turn
        opponent = game.o_player_name
    elif username == game.o_player_name:
        user_playing_x = False
        user_turn = not game.x_turn
        opponent = game.x_player_name
    else:
        raise HTTPException(status_code=403, detail="You are not a player in this game")

    return {
        "status": game.state,
        "grid_properties": game.grid.get_grid_properties(),
        "opponent": opponent,
        "you_playing_x": user_playing_x,
        "your_turn": user_turn,
        "grid_state": game.grid.get_string_array(),
        "play_again_scheme": game.play_again_scheme,
        "play_again_status": game.play_again_status,
        "next_game_id": game.next_game_id
    }


def play_again_accepted(game: Game):
    if (game.play_again_scheme == "alternating" or
            (game.play_again_scheme == "winner_plays_x" and game.state == "won_by_o") or
            (game.play_again_scheme == "winner_plays_o" and game.state == "won_by_x")):
        game.switch_sides = True
    else:
        game.switch_sides = False

    game.next_game_id = game_manager.create_game(x_player=(game.o_player_name if game.switch_sides
                                                           else game.x_player_name),
                                                 o_player=(game.x_player_name if game.switch_sides
                                                           else game.o_player_name),
                                                 size=game.grid.get_grid_properties()["size"],
                                                 winning_line=game.grid.get_grid_properties()["winning_line"],
                                                 play_again_scheme=game.play_again_scheme)
    game.play_again_status = "accepted"


@app.post("/play_again")
async def play_again(details: PlayAgain, username: str = Depends(verify_token)):
    game = game_manager.find_game_by_id(details.game_id)

    if game is None:
        raise HTTPException(status_code=404, detail="Game not found")

    if username != game.x_player_name and username != game.o_player_name:
        raise HTTPException(status_code=403, detail="You are not a player in this game")

    if game.state == "ongoing":
        raise HTTPException(status_code=400, detail="You can't play again until current game is finished")

    if details.play_again:
        if game.play_again_status == "declined":
            raise HTTPException(status_code=409, detail="Play again was declined")

        if game.play_again_status is None:
            game.play_again_status = "requested_by_x" if username == game.x_player_name else "requested_by_o"
            return {"status": "Waiting for opponent to accept"}

        if game.play_again_status == "requested_by_x" and username == game.x_player_name or \
                game.play_again_status == "requested_by_o" and username == game.o_player_name:
            return {"status": "Waiting for opponent to accept"}

        if game.play_again_status == "requested_by_x" and username == game.o_player_name or \
                game.play_again_status == "requested_by_o" and username == game.x_player_name or \
                game.play_again_status == "accepted":
            play_again_accepted(game)
            return {
                "status": "New game started",
                "new_game_id": game.next_game_id,
                "switch_sides": game.switch_sides
            }
    else:
        if game.play_again_status == "accepted":
            return JSONResponse(
                status_code=409,
                content={
                    "detail": "Play again already accepted",
                    "next_game_id": str(game.next_game_id),
                    "switch_sides": game.switch_sides
                }
            )

        game.play_again_status = "declined"
        return {"status": "Play again declined"}


@app.get("/poll_play_again_status")
async def poll_play_again_status(game_id: str, username: str = Depends(verify_token)):
    game = game_manager.find_game_by_id(game_id)

    if game is None:
        raise HTTPException(status_code=404, detail="Game not found")

    if username != game.x_player_name and username != game.o_player_name:
        raise HTTPException(status_code=403, detail="You are not a player in this game")

    if game.play_again_status == "accepted":
        return {
            "play_again_status": game.play_again_status,
            "next_game_id": game.next_game_id,
            "switch_sides": game.switch_sides
        }
    else:
        return {"play_again_status": game.play_again_status}

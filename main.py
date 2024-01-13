from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.security import HTTPBasic, HTTPBasicCredentials, OAuth2PasswordBearer
from fastapi.responses import JSONResponse
from argon2 import PasswordHasher
from argon2.exceptions import Argon2Error
import jwt
import secrets
import re
from schemas import NewMove, Invitation, InvitationResponse, PlayAgain
from database import users, waiting_users, invitations, games, handle_db_exception
from pymongo.errors import PyMongoError, DuplicateKeyError
from bson import ObjectId
from game import create_game, check_if_valid_move, determine_state

app = FastAPI()
security = HTTPBasic()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
ph = PasswordHasher()
secret_key = secrets.token_hex(256)


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
    try:
        username = credentials.username
        password = credentials.password
        validate_username(username)
        validate_password(password)
        hashed_password = ph.hash(password)

        new_user = {
            "username": username,
            "hashed_password": hashed_password
        }

        try:
            users.insert_one(new_user)
        except DuplicateKeyError:
            raise HTTPException(status_code=400, detail="This username is taken")
        except PyMongoError as e:
            handle_db_exception(e)

        token = generate_token(username)
        return {"status": "User created", "token": token}
    except PyMongoError as e:
        handle_db_exception(e)


@app.post("/login")
async def login(credentials: HTTPBasicCredentials = Depends(security)):
    try:
        username = credentials.username
        password = credentials.password

        try:
            user = users.find_one({"username": username})
        except PyMongoError as e:
            handle_db_exception(e)

        if user is None:
            raise HTTPException(status_code=400, detail="Username does not exist")

        try:
            if ph.verify(user["hashed_password"], password):
                token = generate_token(username)
                return {"status": "Logged in", "token": token}
            else:
                raise HTTPException(status_code=400, detail="Incorrect username or password")
        except Argon2Error:
            raise HTTPException(status_code=400, detail="Incorrect username or password")
    except PyMongoError as e:
        handle_db_exception(e)


@app.delete("/delete_account")
async def delete_account(credentials: HTTPBasicCredentials = Depends(security)):
    try:
        username = credentials.username
        password = credentials.password

        try:
            user = users.find_one({"username": username})
        except PyMongoError as e:
            handle_db_exception(e)

        if user is None:
            raise HTTPException(status_code=400, detail="Username does not exist")

        try:
            if ph.verify(user["hashed_password"], password):
                try:
                    users.delete_one({"username": username})
                    return {"status": "Account deleted"}
                except PyMongoError as e:
                    handle_db_exception(e)
            else:
                raise HTTPException(status_code=400, detail="Incorrect username or password")
        except Argon2Error:
            raise HTTPException(status_code=400, detail="Incorrect username or password")
    except PyMongoError as e:
        handle_db_exception(e)


@app.post("/start_waiting")
async def start_waiting(username: str = Depends(verify_token)):
    try:
        waiting_users.insert_one({"username": username})
        return {"status": "Waiting for game"}
    except PyMongoError as e:
        handle_db_exception(e)


@app.post("/stop_waiting")
async def stop_waiting(username: str = Depends(verify_token)):
    try:
        waiting_users.delete_one({"username": username})
        return {"status": "Stopped waiting"}
    except PyMongoError as e:
        handle_db_exception(e)


@app.get("/waiting_users")
async def get_waiting_users(username: str = Depends(verify_token)):
    try:
        result = waiting_users.find({}, {"_id": 0, "username": 1})
        return {"waiting_users": {user["username"] for user in result} - {username}}
    except PyMongoError as e:
        handle_db_exception(e)


@app.post("/invite")
async def invite_user(request_body: Invitation, inviter: str = Depends(verify_token)):
    try:
        if waiting_users.find_one({"username": request_body.invited}) is None:
            raise HTTPException(status_code=400, detail="Invited user is not waiting for a game")

        if request_body.invited == inviter:
            raise HTTPException(status_code=400, detail="You cannot invite yourself")

        if request_body.grid_properties.size < 3 or request_body.grid_properties.size > 26 or \
                request_body.grid_properties.winning_line > request_body.grid_properties.size:
            raise HTTPException(status_code=400, detail="Grid properties not allowed")

        if request_body.play_again_scheme not in {"same", "alternating", "winner_plays_x", "winner_plays_o"}:
            raise HTTPException(status_code=400, detail="Unknown play again scheme")

        new_invitation = {
            "inviter": inviter,
            "invited": request_body.invited,
            "grid_properties": {
                "size": request_body.grid_properties.size,
                "winning_line": request_body.grid_properties.winning_line
            },
            "inviter_playing_x": request_body.inviter_playing_x,
            "play_again_scheme": request_body.play_again_scheme,
            "status": "pending",
            "game_id": None
        }

        invitation_id = str(invitations.insert_one(new_invitation).inserted_id)
        return {"invitation_id": invitation_id}
    except PyMongoError as e:
        handle_db_exception(e)


@app.get("/poll_invitations")
async def poll_invitations(username: str = Depends(verify_token)):
    try:
        result = invitations.find({"invited": username, "status": "pending"})
        invitations_list = []
        for invitation in result:
            invitation_details = {
                "invitation_id": str(invitation["_id"]),
                "inviter": invitation["inviter"],
                "grid_properties": invitation["grid_properties"],
                "inviter_playing_x": invitation["inviter_playing_x"],
                "play_again_scheme": invitation["play_again_scheme"]
            }
            invitations_list.append(invitation_details)
        return {"invitations": invitations_list}
    except PyMongoError as e:
        handle_db_exception(e)


@app.get("/poll_invitation_status")
async def poll_invitation_status(invitation_id: str, username: str = Depends(verify_token)):
    try:
        invitation = invitations.find_one({"_id": ObjectId(invitation_id)})
        if invitation is None:
            raise HTTPException(status_code=404, detail="Invitation not found")
        if invitation["inviter"] != username:
            raise HTTPException(status_code=403, detail="This invitation is not yours")

        status = invitation["status"]
        if status == "accepted":
            return {"status": status, "game_id": invitation["game_id"]}
        else:
            return {"status": status}
    except PyMongoError as e:
        handle_db_exception(e)


@app.post("/respond_invitation")
async def respond_invitation(request_body: InvitationResponse, username: str = Depends(verify_token)):
    try:
        invitation_id = request_body.invitation_id
        response = request_body.response

        invitation = invitations.find_one({"_id": ObjectId(invitation_id)})
        if invitation is None:
            raise HTTPException(status_code=404, detail="Invitation not found")

        if response.lower() == "accept":
            if invitation and invitation["invited"] == username and invitation["status"] == "pending":
                size = invitation["grid_properties"]["size"]
                winning_line = invitation["grid_properties"]["winning_line"]

                if invitation["inviter_playing_x"]:
                    game_id = create_game(invitation["inviter"], invitation["invited"],
                                          size, winning_line, invitation["play_again_scheme"])
                else:
                    game_id = create_game(invitation["invited"], invitation["inviter"],
                                          size, winning_line, invitation["play_again_scheme"])

                waiting_users.delete_one({"username": invitation["inviter"]})
                waiting_users.delete_one({"username": invitation["invited"]})

                invitations.update_one({"_id": ObjectId(invitation_id)},
                                       {"$set": {"status": "accepted", "game_id": game_id}})

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
            invitations.update_one({"_id": ObjectId(invitation_id)}, {"$set": {"status": "declined"}})
            return {"detail": "Invitation declined"}
        else:
            raise HTTPException(status_code=400, detail="Invalid response")
    except PyMongoError as e:
        handle_db_exception(e)


@app.post("/cancel_invitation")
async def cancel_invitation(invitation_id: str, username: str = Depends(verify_token)):
    try:
        invitations.update_one({"_id": ObjectId(invitation_id)}, {"$set": {"status": "cancelled"}})
        return {"detail": "Invitation cancelled"}
    except PyMongoError as e:
        handle_db_exception(e)


@app.get("/get_sent_invitations")
async def get_sent_invitations(username: str = Depends(verify_token)):
    try:
        result = invitations.find({"invited": username, "status": "pending"})
        invitations_list = []
        for invitation in result:
            invitation_details = {
                "invitation_id": str(invitation["_id"]),
                "invited": invitation["invited"],
                "grid_properties": invitation["grid_properties"],
                "inviter_playing_x": invitation["inviter_playing_x"],
                "play_again_scheme": invitation["play_again_scheme"],
                "status": invitation["status"],
                "game_id": invitation["game_id"]
            }
            invitations_list.append(invitation_details)
        return {"invitations": invitations_list}
    except PyMongoError as e:
        handle_db_exception(e)


@app.post("/make_move")
async def make_move(new_move: NewMove, username: str = Depends(verify_token)):
    try:
        game_id = new_move.game_id
        cell = new_move.cell

        game = games.find_one({"_id": ObjectId(game_id)})
        if game is None:
            raise HTTPException(status_code=404, detail="Game not found")

        if username != game["x_player_name"] and username != game["o_player_name"]:
            raise HTTPException(status_code=403, detail="You are not a player in this game")

        try:
            if username not in [game["x_player_name"], game["o_player_name"]]:
                raise ValueError("Player does not exist in this game!")
            elif not game["state"] == "ongoing":
                raise ValueError("Game is finished")
            elif (game["x_turn"] and username != game["x_player_name"]) or \
                    (not game["x_turn"] and username != game["o_player_name"]):
                raise ValueError("It's not your turn!")
            elif not check_if_valid_move(game["grid_state"], cell):
                raise ValueError("Invalid move!")

            else:
                token = 'X' if game["x_turn"] else 'O'
                row = ord(cell[0].lower()) - ord('a')
                column = int(cell[1:]) - 1

                grid = game["grid_state"]
                grid[row][column] = token
                new_state = determine_state(grid, game["grid_properties"]["winning_line"])

                if new_state == game["state"]:
                    update = {
                        "$set": {
                            "grid_state": grid,
                            "last_move": {"player_name": username, "cell": cell},
                            "x_turn": not game["x_turn"]
                        }
                    }
                else:
                    update = {
                        "$set": {
                            "grid_state": grid,
                            "last_move": {"player_name": username, "cell": cell},
                            "x_turn": not game["x_turn"],
                            "state": new_state
                        }
                    }

                games.update_one({"_id": ObjectId(game_id)}, update)

        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        return {"game_state": new_state}
    except PyMongoError as e:
        handle_db_exception(e)


@app.get("/poll_game")
async def poll_game(game_id: str, username: str = Depends(verify_token)):
    try:
        game = games.find_one({"_id": ObjectId(game_id)})
        if game is None:
            raise HTTPException(status_code=404, detail="Game not found")

        if username != game["x_player_name"] and username != game["o_player_name"]:
            raise HTTPException(status_code=403, detail="You are not a player in this game")

        last_move = game["last_move"]

        if last_move and last_move["player_name"] != username:
            return {
                "new_move": True,
                "cell": last_move["cell"],
                "game_state": game["state"]
            }
        else:
            return {
                "new_move": False,
                "game_state": game["state"]
            }
    except PyMongoError as e:
        handle_db_exception(e)


@app.get("/get_ongoing_games")
async def get_ongoing_games(username: str = Depends(verify_token)):
    try:
        search_query = {
            "$or": [
                {"x_player_name": username},
                {"o_player_name": username}
            ]
        }

        result = games.find(search_query)

        games_list = []
        for game in result:
            game_details = {
                "game_id": str(game["_id"]),
                "opponent": (game["o_player_name"] if username == game["x_player_name"] else game["x_player_name"]),
                "grid_properties": game["grid_properties"],
                "you_playing_x": (username == game["x_player_name"]),
                "play_again_scheme": game["play_again_scheme"]
            }
            games_list.append(game_details)

        return {"ongoing_games": games_list}
    except PyMongoError as e:
        handle_db_exception(e)


@app.get("/get_full_game_state")
async def get_full_game_state(game_id: str, username: str = Depends(verify_token)):
    try:
        game = games.find_one({"_id": ObjectId(game_id)})
        if game is None:
            raise HTTPException(status_code=404, detail="Game not found")

        if username == game["x_player_name"]:
            user_playing_x = True
            user_turn = game["x_turn"]
            opponent = game["o_player_name"]
        elif username == game["o_player_name"]:
            user_playing_x = False
            user_turn = not game["x_turn"]
            opponent = game["x_player_name"]
        else:
            raise HTTPException(status_code=403, detail="You are not a player in this game")

        return {
            "status": game["state"],
            "grid_properties": game["grid_properties"],
            "opponent": opponent,
            "you_playing_x": user_playing_x,
            "your_turn": user_turn,
            "grid_state": game["grid_state"],
            "play_again_scheme": game["play_again_scheme"],
            "play_again_status": game["play_again_status"],
            "next_game_id": game["next_game_id"]
        }
    except PyMongoError as e:
        handle_db_exception(e)


def play_again_accepted(game: dict):
    try:
        if (game["play_again_scheme"] == "alternating" or
                (game["play_again_scheme"] == "winner_plays_x" and game["state"] == "won_by_o") or
                (game["play_again_scheme"] == "winner_plays_o" and game["state"] == "won_by_x")):
            game["switch_sides"] = True
        else:
            game["switch_sides"] = False

        game["next_game_id"] = create_game(x_player=(game["o_player_name"] if game["switch_sides"]
                                                     else game["x_player_name"]),
                                           o_player=(game["x_player_name"] if game["switch_sides"]
                                                     else game["o_player_name"]),
                                           size=game["grid_properties"]["size"],
                                           winning_line=game["grid_properties"]["winning_line"],
                                           play_again_scheme=game["play_again_scheme"])

        update = {
            "$set": {
                "play_again_status": "accepted",
                "switch_sides": game["switch_sides"],
                "next_game_id": game["next_game_id"]
            }
        }
        games.update_one({"_id": ObjectId(game["_id"])}, update)
    except PyMongoError as e:
        handle_db_exception(e)


@app.post("/play_again")
async def play_again(request_body: PlayAgain, username: str = Depends(verify_token)):
    try:
        game = games.find_one({"_id": ObjectId(request_body.game_id)})

        if game is None:
            raise HTTPException(status_code=404, detail="Game not found")

        if username != game["x_player_name"] and username != game["o_player_name"]:
            raise HTTPException(status_code=403, detail="You are not a player in this game")

        if game["state"] == "ongoing":
            raise HTTPException(status_code=400, detail="You can't play again until current game is finished")

        if request_body.play_again:
            if game["play_again_status"] == "declined":
                raise HTTPException(status_code=409, detail="Play again was declined")

            if game["play_again_status"] is None:
                game["play_again_status"] = "requested_by_x" if username == game["x_player_name"] else "requested_by_o"
                update = {"$set": {"play_again_status": "requested_by_x"
                                                        if username == game["x_player_name"]
                                                        else "requested_by_o"}}
                games.update_one({"_id": ObjectId(request_body.game_id)}, update)
                return {"status": "Waiting for opponent to accept"}

            if game["play_again_status"] == "requested_by_x" and username == game["x_player_name"] or \
                    game["play_again_status"] == "requested_by_o" and username == game["o_player_name"]:
                return {"status": "Waiting for opponent to accept"}

            if game["play_again_status"] == "requested_by_x" and username == game["o_player_name"] or \
                    game["play_again_status"] == "requested_by_o" and username == game["x_player_name"]:
                play_again_accepted(game)
                return {
                    "status": "New game started",
                    "new_game_id": game["next_game_id"],
                    "switch_sides": game["switch_sides"]
                }

            if game["play_again_status"] == "accepted":
                return {
                    "status": "New game started",
                    "new_game_id": game["next_game_id"],
                    "switch_sides": game["switch_sides"]
                }

        else:
            if game["play_again_status"] == "accepted":
                return JSONResponse(
                    status_code=409,
                    content={
                        "detail": "Play again already accepted",
                        "next_game_id": game["next_game_id"],
                        "switch_sides": game["switch_sides"]
                    }
                )

            games.update_one({"_id": ObjectId(game["_id"])}, {"$set": {"play_again_status": "declined"}})
            return {"status": "Play again declined"}
    except PyMongoError as e:
        handle_db_exception(e)


@app.get("/poll_play_again_status")
async def poll_play_again_status(game_id: str, username: str = Depends(verify_token)):
    try:
        game = games.find_one({"_id": ObjectId(game_id)})

        if game is None:
            raise HTTPException(status_code=404, detail="Game not found")

        if username != game["x_player_name"] and username != game["o_player_name"]:
            raise HTTPException(status_code=403, detail="You are not a player in this game")

        if game["play_again_status"] == "accepted":
            return {
                "play_again_status": game["play_again_status"],
                "next_game_id": game["next_game_id"],
                "switch_sides": game["switch_sides"]
            }
        else:
            return {"play_again_status": game["play_again_status"]}
    except PyMongoError as e:
        handle_db_exception(e)

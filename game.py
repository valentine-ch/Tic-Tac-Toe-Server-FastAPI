# from grid import Grid, States
# import uuid
from database import games


# class Game:
#     def __init__(self, x_player: str, o_player: str,
#                  size: int, winning_line: int, play_again_scheme: str):
#         self.x_player_name = x_player
#         self.o_player_name = o_player
#         self.grid = Grid(size, winning_line)
#         self.x_turn = True
#         self.last_move = None
#         self.state = "ongoing"
#         self.play_again_scheme = play_again_scheme
#         self.play_again_status = None
#         self.next_game_id = None
#         self.switch_sides = None
#
#     def update_state(self):
#         if self.grid.has_won(States.X):
#             self.state = "won_by_x"
#         elif self.grid.has_won(States.O):
#             self.state = "won_by_o"
#         elif self.grid.is_draw():
#             self.state = "draw"
#
#     def make_move(self, player_name: str, cell: str):
#         if player_name not in [self.x_player_name, self.o_player_name]:
#             raise ValueError("Player does not exist in this game!")
#         elif (self.x_turn and player_name != self.x_player_name) or \
#                 (not self.x_turn and player_name != self.o_player_name):
#             raise ValueError("It's not your turn!")
#         elif not self.grid.is_valid_move(cell):
#             raise ValueError("Invalid move!")
#         elif not self.state == "ongoing":
#             raise ValueError("Game is finished")
#
#         else:
#             token = States.X if self.x_turn else States.O
#             self.grid.update_grid(cell, token)
#             self.update_state()
#             self.last_move = {"player_name": player_name, "cell": cell}
#             self.x_turn = not self.x_turn
#
#
# class GameManager:
#     def __init__(self):
#         self.games = {}
#
#     def create_game(self, x_player: str, o_player: str,
#                     size: int, winning_line: int, play_again_scheme: str):
#         game_id = str(uuid.uuid4())
#         new_game = Game(x_player, o_player, size, winning_line, play_again_scheme)
#         self.games[game_id] = new_game
#         return game_id
#
#     def find_game_by_id(self, game_id: str):
#         return self.games.get(game_id)
#
#     def get_ongoing_games_by_username(self, username: str):
#         games = []
#         for id, game in self.games.items():
#             if game.state == "ongoing" and (username == game.x_player_name or username == game.o_player_name):
#                 game_details = {
#                     "game_id": id,
#                     "opponent": (game.o_player_name if username == game.x_player_name
#                                  else game.x_player_name),
#                     "grid_properties": game.grid.get_grid_properties(),
#                     "you_playing_x": (username == game.x_player_name),
#                     "play_again_scheme": game.play_again_scheme
#                 }
#                 games.append(game_details)
#         return games


def create_game(x_player: str, o_player: str, size: int, winning_line: int, play_again_scheme: str):
    new_game = {
        "x_player_name": x_player,
        "o_player_name": o_player,
        "grid_properties": {
            "size": size,
            "winning_line": winning_line
        },
        "grid_state": [['' for _ in range(size)] for _ in range(size)],
        "x_turn": True,
        "last_move": None,
        "state": "ongoing",
        "play_again_scheme": play_again_scheme,
        "play_again_status": None,
        "next_game_id": None,
        "switch_sides": None
    }

    game_id = str(games.insert_one(new_game).inserted_id)
    return game_id


def check_if_valid_move(grid: list, cell: str):
    row = ord(cell[0].lower()) - ord('a')
    column = int(cell[1:]) - 1

    if row >= 0 and row < len(grid) and column >= 0 and column < len(grid):
        if grid[row][column] == '':
            return True
    return False


def check_if_won(grid: list, winning_line: int, token: str):
    # check rows
    for i in range(len(grid)):
        for j in range(len(grid) - winning_line + 1):
            win = all(grid[i][j + k] == token for k in range(winning_line))
            if win:
                return True

    # check columns
    for j in range(len(grid)):
        for i in range(len(grid) - winning_line + 1):
            win = all(grid[i + k][j] == token for k in range(winning_line))
            if win:
                return True

    # check diagonals (top-left to bottom-right)
    for i in range(len(grid) - winning_line + 1):
        for j in range(len(grid) - winning_line + 1):
            win = all(grid[i + k][j + k] == token for k in range(winning_line))
            if win:
                return True

    # check diagonals (top-right to bottom-left)
    for i in range(len(grid) - winning_line + 1):
        for j in range(winning_line - 1, len(grid)):
            win = all(grid[i + k][j - k] == token for k in range(winning_line))
            if win:
                return True

    # no winning condition met
    return False


def check_if_is_draw(grid: list):
    for row in grid:
        if any(cell == '' for cell in row):
            return False
    return True


def determine_state(grid: list, winning_line: int):
    if check_if_won(grid, winning_line, 'X'):
        return "won_by_x"
    elif check_if_won(grid, winning_line, 'O'):
        return "won_by_o"
    elif check_if_is_draw(grid):
        return "draw"
    else:
        return "ongoing"

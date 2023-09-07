from grid import Grid, States
import uuid


class Game:
    def __init__(self, x_player: str, o_player: str,
                 size: int, winning_line: int, play_again_scheme: str):
        self.id = uuid.uuid4()
        self.x_player_name = x_player
        self.o_player_name = o_player
        self.grid = Grid(size, winning_line)
        self.x_turn = True
        self.last_move = None
        self.state = "ongoing"
        self.play_again_scheme = play_again_scheme
        self.play_again_status = None
        self.next_game_id = None
        self.switch_sides = None

    def update_state(self):
        if self.grid.has_won(States.X):
            self.state = "won_by_x"
        elif self.grid.has_won(States.O):
            self.state = "won_by_o"
        elif self.grid.is_draw():
            self.state = "draw"

    def make_move(self, player_name: str, cell: str):
        if player_name not in [self.x_player_name, self.o_player_name]:
            raise ValueError("Player does not exist in this game!")
        elif (self.x_turn and player_name != self.x_player_name) or \
                (not self.x_turn and player_name != self.o_player_name):
            raise ValueError("It's not your turn!")
        elif not self.grid.is_valid_move(cell):
            raise ValueError("Invalid move!")
        elif not self.state == "ongoing":
            raise ValueError("Game is finished")

        else:
            token = States.X if self.x_turn else States.O
            self.grid.update_grid(cell, token)
            self.update_state()
            self.last_move = {"player_name": player_name, "cell": cell}
            self.x_turn = not self.x_turn


class GameManager:
    def __init__(self):
        self.games = {}

    def create_game(self, x_player: str, o_player: str,
                    size: int, winning_line: int, play_again_scheme: str):
        new_game = Game(x_player, o_player, size, winning_line, play_again_scheme)
        self.games[str(new_game.id)] = new_game
        return new_game.id

    def find_game_by_id(self, game_id: str):
        return self.games.get(game_id)

    def get_ongoing_games_by_username(self, username: str):
        games = []
        for id, game in self.games.items():
            if game.state == "ongoing" and (username == game.x_player_name or username == game.o_player_name):
                game_details = {
                    "game_id": id,
                    "opponent": (game.o_player_name if username == game.x_player_name
                                 else game.x_player_name),
                    "grid_properties": game.grid.get_grid_properties(),
                    "you_playing_x": (username == game.x_player_name),
                    "play_again_scheme": game.play_again_scheme
                }
                games.append(game_details)
        return games

from database import games


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

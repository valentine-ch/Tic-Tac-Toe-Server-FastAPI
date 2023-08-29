from enum import Enum


class States(Enum):
    EMPTY = 0
    X = 1
    O = 2


class Grid:
    def __init__(self, size: int, winning_line: int):
        self.__size = size
        self.__winning_line = winning_line
        self.__grid = [[States.EMPTY for _ in range(size)]
                       for _ in range(size)]

    def clear(self):
        for i in self.__grid:
            for j in i:
                self.__grid[i][j] = States.EMPTY

    def is_valid_move(self, move: str):
        row = ord(move[0].lower()) - ord('a')
        column = int(move[1:]) - 1

        # Now check if the move is valid
        if row >= 0 and row < self.__size and column >= 0 and column < self.__size:
            if self.__grid[row][column] == States.EMPTY:
                return True

        return False

    def update_grid(self, move: str, token: States):
        if not self.is_valid_move(move):
            raise ValueError("Invalid move")

        row = ord(move[0].lower()) - ord('a')
        column = int(move[1:]) - 1
        self.__grid[row][column] = token

    def has_won(self, side: States) -> bool:
        # check rows
        for i in range(self.__size):
            for j in range(self.__size - self.__winning_line + 1):
                win = all(self.__grid[i][j + k] == side for k in range(self.__winning_line))
                if win:
                    return True

        # check columns
        for j in range(self.__size):
            for i in range(self.__size - self.__winning_line + 1):
                win = all(self.__grid[i + k][j] == side for k in range(self.__winning_line))
                if win:
                    return True

        # check diagonals (top-left to bottom-right)
        for i in range(self.__size - self.__winning_line + 1):
            for j in range(self.__size - self.__winning_line + 1):
                win = all(self.__grid[i + k][j + k] == side for k in range(self.__winning_line))
                if win:
                    return True

        # check diagonals (top-right to bottom-left)
        for i in range(self.__size - self.__winning_line + 1):
            for j in range(self.__winning_line - 1, self.__size):
                win = all(self.__grid[i + k][j - k] == side for k in range(self.__winning_line))
                if win:
                    return True

        # no winning condition met
        return False

    def is_draw(self) -> bool:
        for row in self.__grid:
            if any(cell == States.EMPTY for cell in row):
                return False
        return True

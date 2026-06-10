"""Command-line Tic Tac Toe game.

Run with:
    python tic_tac_toe.py
"""

from __future__ import annotations

from dataclasses import dataclass, field

BOARD_SIZE = 3
EMPTY = " "
PLAYERS = ("X", "O")
WINNING_LINES = (
    (0, 1, 2),
    (3, 4, 5),
    (6, 7, 8),
    (0, 3, 6),
    (1, 4, 7),
    (2, 5, 8),
    (0, 4, 8),
    (2, 4, 6),
)


@dataclass
class TicTacToe:
    """Stores game state and rules for a two-player Tic Tac Toe game."""

    board: list[str] = field(default_factory=lambda: [EMPTY] * (BOARD_SIZE**2))
    current_player: str = PLAYERS[0]

    def render(self) -> str:
        """Return a printable board; empty squares show their move number."""
        cells = [value if value != EMPTY else str(index + 1) for index, value in enumerate(self.board)]
        rows = [" | ".join(cells[i : i + BOARD_SIZE]) for i in range(0, len(cells), BOARD_SIZE)]
        return "\n---------\n".join(rows)

    def make_move(self, square: int) -> None:
        """Place the current player's mark on a 1-based board square."""
        index = square - 1
        if square < 1 or square > BOARD_SIZE**2:
            raise ValueError("請輸入 1 到 9 之間的數字。")
        if self.board[index] != EMPTY:
            raise ValueError("這個位置已經被佔用了，請選擇其他位置。")

        self.board[index] = self.current_player

    def winner(self) -> str | None:
        """Return the winning player mark, or None if there is no winner yet."""
        for a, b, c in WINNING_LINES:
            if self.board[a] != EMPTY and self.board[a] == self.board[b] == self.board[c]:
                return self.board[a]
        return None

    def is_draw(self) -> bool:
        """Return True when the board is full and no player has won."""
        return self.winner() is None and all(cell != EMPTY for cell in self.board)

    def switch_player(self) -> None:
        """Switch turns between X and O."""
        self.current_player = PLAYERS[1] if self.current_player == PLAYERS[0] else PLAYERS[0]


def prompt_square(player: str) -> int:
    """Ask a player for the next square number."""
    raw_value = input(f"玩家 {player}，請選擇位置 (1-9)：").strip()
    if not raw_value.isdigit():
        raise ValueError("請輸入數字。")
    return int(raw_value)


def play() -> None:
    """Start an interactive command-line game."""
    game = TicTacToe()
    print("井字遊戲 Tic Tac Toe")
    print("輪流輸入 1-9 選擇位置，先連成一線者獲勝。\n")

    while True:
        print(game.render())
        print()

        try:
            game.make_move(prompt_square(game.current_player))
        except ValueError as error:
            print(f"錯誤：{error}\n")
            continue

        if game.winner():
            print(game.render())
            print(f"\n玩家 {game.current_player} 獲勝！")
            break

        if game.is_draw():
            print(game.render())
            print("\n平手！")
            break

        game.switch_player()
        print()


if __name__ == "__main__":
    play()

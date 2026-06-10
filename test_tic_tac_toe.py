import pytest

from tic_tac_toe import TicTacToe


def test_x_wins_top_row():
    game = TicTacToe()
    for square in (1, 4, 2, 5, 3):
        game.make_move(square)
        if game.winner() is None:
            game.switch_player()

    assert game.winner() == "X"


def test_draw_when_board_full_without_winner():
    game = TicTacToe()
    for square in (1, 2, 3, 5, 4, 6, 8, 7, 9):
        game.make_move(square)
        if game.winner() is None:
            game.switch_player()

    assert game.winner() is None
    assert game.is_draw()


def test_rejects_occupied_square():
    game = TicTacToe()
    game.make_move(1)

    with pytest.raises(ValueError, match="已經被佔用"):
        game.make_move(1)


def test_rejects_out_of_range_square():
    game = TicTacToe()

    with pytest.raises(ValueError, match="1 到 9"):
        game.make_move(10)

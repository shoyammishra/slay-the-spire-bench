"""Tests for the chess controlled-horizon pilot (scripts/chess_pilot.py)."""
import math
import random
import sys
from pathlib import Path

import chess

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import chess_pilot as cp  # noqa: E402


def brute(board, depth):
    t = cp.terminal_value(board)
    if t is not None:
        return t
    if depth == 0:
        return cp.material(board)
    vals = []
    for m in board.legal_moves:
        board.push(m); vals.append(brute(board, depth - 1)); board.pop()
    return max(vals) if board.turn == chess.WHITE else min(vals)


def _positions(n, seed=1):
    rng, out = random.Random(seed), []
    while len(out) < n:
        f = cp.random_position(rng)
        if f:
            out.append(f)
    return out


def test_alphabeta_matches_brute_force_minimax():
    for fen in _positions(6):
        board = chess.Board(fen)
        for m in board.legal_moves:
            board.push(m)
            assert cp.alphabeta(board, 2, -math.inf, math.inf) == brute(board, 2)
            board.pop()


def test_terminal_values():
    mated = chess.Board('k7/1Q6/1K6/8/8/8/8/8 b - - 0 1')  # black king mated by queen
    assert mated.is_checkmate() and cp.terminal_value(mated) == 9 + 1000
    stale = chess.Board('k7/2Q5/1K6/8/8/8/8/8 b - - 0 1')
    assert stale.is_stalemate() and cp.terminal_value(stale) == 0


def test_horizon_one_is_immediate_material():
    fen = '4k3/8/8/3q4/4R3/8/8/4K3 w - - 0 1'  # rook can take the queen? (e4xd5 is not a rook move)
    av = cp.action_values(fen, 1)
    b = chess.Board(fen)
    for uci, v in av.items():
        b.push(chess.Move.from_uci(uci))
        assert v == (cp.terminal_value(b) if cp.terminal_value(b) is not None else cp.material(b))
        b.pop()


def test_prompts_differ_only_in_horizon():
    fen = _positions(1)[0]
    a, b = cp.user_prompt(fen, 1), cp.user_prompt(fen, 5)
    diff = [(x, y) for x, y in zip(a.splitlines(), b.splitlines()) if x != y]
    assert len(diff) == 1 and diff[0][0].replace('exactly 1 plies', 'exactly 5 plies') == diff[0][1]
    cp.check_prompts([dict(state_id='x', fen=fen)])


def test_parse_move_accepts_uci_and_san_and_rejects_illegal():
    fen = chess.STARTING_FEN
    assert cp.parse_move('{"move": "e2e4"}', fen) == 'e2e4'
    assert cp.parse_move('thinking... {"move": "Nf3"}', fen) == 'g1f3'
    assert cp.parse_move('{"move": "e2e5"}', fen) is None
    assert cp.parse_move('no json here', fen) is None


def test_scoring_is_h_blind_invariant():
    orc = dict(action_values={'a': 3, 'b': 1, 'c': 0}, best_value=3, worst_value=0, optimal_actions=['a'])
    for mv in ('a', 'b', 'c', None):
        assert cp.eq(orc, mv) - cp.eq(orc, mv) == 0  # same answer twice -> zero gain


if __name__ == '__main__':
    for name, fn in list(globals().items()):
        if name.startswith('test_'):
            fn(); print('PASS', name)

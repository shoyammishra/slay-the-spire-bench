"""Controlled-horizon pilot in a second domain: small chess endgames (Amendment 9).

Same construction as the card-game benchmark, in a different simulator:
  * a frozen state (a legal position, White to move, each king plus two pieces);
  * a goal measured after exactly H plies, H in {1, 5}: material balance from White's view
    (P=1, N=B=3, R=5, Q=9), +1000 if Black is checkmated, -1000 if White is, 0 for a draw,
    with Black choosing replies that minimise it;
  * an exact oracle: full-window alpha-beta minimax from every legal first move;
  * prompts that differ only in the number H;
  * sensitive states (best-move sets at H=1 and H=5 disjoint) and controls (they overlap).

Actions:
  build    generate positions, compute exact values, write the release JSON
  run      query an OpenAI-compatible endpoint, append rows (resumable, no retries)
  analyze  primary statistic, sensitive/control gains, use vs H-blind baseline, answer changes
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import hashlib
import json
import math
import random
import re
import sys
import time
import urllib.request
from pathlib import Path

import chess

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results' / 'chess_pilot'
HORIZONS = (1, 5)
VALUES = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 0}
MATE = 1000
PIECES = (chess.QUEEN, chess.ROOK, chess.BISHOP, chess.KNIGHT, chess.PAWN)

SYSTEM = ('You are an expert chess player. You will be shown a chess position with White to move. '
          'Answer with a single JSON object of the form {"move": "<uci>"} where <uci> is one of the '
          'listed legal moves, for example {"move": "e2e4"}. Output nothing after the JSON object.')


# ---------------------------------------------------------------- oracle
def material(board: chess.Board) -> int:
    s = 0
    for piece in board.piece_map().values():
        s += VALUES[piece.piece_type] * (1 if piece.color == chess.WHITE else -1)
    return s


def terminal_value(board: chess.Board):
    """Utility if the game is over, else None (automatic outcomes only; no draw claims)."""
    if board.is_checkmate():
        return material(board) + (-MATE if board.turn == chess.WHITE else MATE)
    if board.is_stalemate() or board.is_insufficient_material():
        return 0
    return None


def _ordered(board: chess.Board):
    moves = list(board.legal_moves)
    moves.sort(key=lambda m: (not board.is_capture(m), m.promotion is None, m.uci()))
    return moves


def alphabeta(board: chess.Board, depth: int, alpha: float, beta: float) -> int:
    t = terminal_value(board)
    if t is not None:
        return t
    if depth == 0:
        return material(board)
    if board.turn == chess.WHITE:
        best = -math.inf
        for m in _ordered(board):
            board.push(m)
            v = alphabeta(board, depth - 1, alpha, beta)
            board.pop()
            best = max(best, v); alpha = max(alpha, v)
            if alpha >= beta:
                break
        return best
    best = math.inf
    for m in _ordered(board):
        board.push(m)
        v = alphabeta(board, depth - 1, alpha, beta)
        board.pop()
        best = min(best, v); beta = min(beta, v)
        if alpha >= beta:
            break
    return best


def action_values(fen: str, horizon: int) -> dict:
    """Exact value of every legal first move: utility after exactly `horizon` plies."""
    board = chess.Board(fen)
    out = {}
    for m in sorted(board.legal_moves, key=lambda x: x.uci()):
        board.push(m)
        out[m.uci()] = int(alphabeta(board, horizon - 1, -math.inf, math.inf))
        board.pop()
    return out


def oracle_entry(fen: str) -> dict:
    res = {}
    for h in HORIZONS:
        av = action_values(fen, h)
        best, worst = max(av.values()), min(av.values())
        res[str(h)] = dict(action_values=av, best_value=best, worst_value=worst,
                           optimal_actions=sorted(k for k, v in av.items() if v == best))
    o1, o5 = set(res['1']['optimal_actions']), set(res[str(HORIZONS[-1])]['optimal_actions'])
    return dict(fen=fen, oracles=res, sensitive=not (o1 & o5))


# ---------------------------------------------------------------- positions
def random_position(rng: random.Random):
    """Each king plus two pieces, White to move, with at least one capture available (so the
    one-ply goal discriminates between moves); None if illegal or trivial."""
    board = chess.Board(None)
    squares = rng.sample(range(64), 6)
    board.set_piece_at(squares[0], chess.Piece(chess.KING, chess.WHITE))
    board.set_piece_at(squares[1], chess.Piece(chess.KING, chess.BLACK))
    spec = [(rng.choice(PIECES), chess.WHITE), (rng.choice(PIECES), chess.WHITE),
            (rng.choice(PIECES), chess.BLACK), (rng.choice(PIECES), chess.BLACK)]
    for sq, (pt, col) in zip(squares[2:], spec):
        if pt == chess.PAWN and chess.square_rank(sq) in (0, 7):
            return None
        board.set_piece_at(sq, chess.Piece(pt, col))
    board.turn = chess.WHITE
    if not board.is_valid() or board.is_game_over():
        return None
    if board.legal_moves.count() < 3 or not any(board.is_capture(m) for m in board.legal_moves):
        return None
    return board.fen()


def _oracle_job(fen):
    return oracle_entry(fen)


def build(args):
    rng = random.Random(args.seed)
    fens, seen = [], set()
    while len(fens) < args.candidates:
        f = random_position(rng)
        if f and f not in seen:
            seen.add(f); fens.append(f)
    t0 = time.time()
    with cf.ProcessPoolExecutor(max_workers=args.workers) as ex:
        entries = list(ex.map(_oracle_job, fens, chunksize=4))
    print(f'oracle: {len(entries)} positions in {time.time() - t0:.0f}s', flush=True)
    # Keep states where both horizons discriminate between moves.
    usable = [e for e in entries if all(e['oracles'][str(h)]['best_value'] > e['oracles'][str(h)]['worst_value']
                                         for h in HORIZONS)]
    sens = [e for e in usable if e['sensitive']]
    ctrl = [e for e in usable if not e['sensitive']]
    n = min(args.per_set, len(sens), len(ctrl))
    keep = sens[:n] + ctrl[:n]
    for i, e in enumerate(keep):
        e['state_id'] = f'chess-pilot-{i:04d}'
    release = dict(version='chess-pilot-v1', seed=args.seed, horizons=list(HORIZONS),
                   utility='material after exactly H plies (P1 N3 B3 R5 Q9), +-1000 mate, 0 draw; Black minimises',
                   counts=dict(candidates=len(entries), usable=len(usable), sensitive_available=len(sens),
                               control_available=len(ctrl), kept_per_set=n),
                   states=keep)
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / 'release.json'
    path.write_text(json.dumps(release, indent=1), encoding='utf-8')
    print(json.dumps(release['counts']), 'sha256', hashlib.sha256(path.read_bytes()).hexdigest())


# ---------------------------------------------------------------- prompts
def board_text(fen: str) -> str:
    board = chess.Board(fen)
    rows = []
    for rank in range(7, -1, -1):
        cells = []
        for file in range(8):
            p = board.piece_at(chess.square(file, rank))
            cells.append(p.symbol() if p else '.')
        rows.append(f'{rank + 1} ' + ' '.join(cells))
    rows.append('  a b c d e f g h')
    return '\n'.join(rows)


def user_prompt(fen: str, horizon: int) -> str:
    board = chess.Board(fen)
    legal = ' '.join(sorted(m.uci() for m in board.legal_moves))
    return (f'Position (FEN): {fen}\n'
            f'Board (White pieces uppercase, Black lowercase):\n{board_text(fen)}\n'
            f'White to move. Legal moves (UCI): {legal}\n\n'
            'Utility is the material balance from White\'s point of view (pawn 1, knight 3, bishop 3, '
            'rook 5, queen 9), plus 1000 if Black is checkmated, minus 1000 if White is checkmated, '
            'and exactly 0 if the game is drawn. Each move by either side is one ply. Black always '
            'replies to minimise the utility. The game is scored at the moment it ends, if it ends earlier.\n'
            f'Choose the move that maximizes the utility after exactly {horizon} plies, counting your move as ply 1.')


def check_prompts(states) -> None:
    for s in states:
        a, b = (user_prompt(s['fen'], h) for h in HORIZONS)
        diff = [(x, y) for x, y in zip(a.splitlines(), b.splitlines()) if x != y]
        assert len(a.splitlines()) == len(b.splitlines()) and len(diff) == 1, s['state_id']


# ---------------------------------------------------------------- inference
def parse_move(text: str, fen: str):
    board = chess.Board(fen)
    for m in re.finditer(r'\{[^{}]*\}', text or ''):
        try:
            obj = json.loads(m.group(0))
        except ValueError:
            continue
        mv = str(obj.get('move', '')).strip()
        try:
            move = chess.Move.from_uci(mv)
            if move in board.legal_moves:
                return move.uci()
        except ValueError:
            pass
        try:
            return board.parse_san(mv).uci()
        except ValueError:
            return None
    return None


def query(base, model, fen, horizon, max_tokens, timeout):
    payload = dict(model=model, temperature=0, top_p=1, seed=42, max_tokens=max_tokens,
                   messages=[dict(role='system', content=SYSTEM), dict(role='user', content=user_prompt(fen, horizon))])
    req = urllib.request.Request(base + '/v1/chat/completions', data=json.dumps(payload).encode(),
                                 headers={'Content-Type': 'application/json'})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        resp = json.loads(r.read())
    ch = resp['choices'][0]
    return dict(content=ch['message'].get('content'), reasoning=ch['message'].get('reasoning_content'),
                finish_reason=ch.get('finish_reason'), usage=resp.get('usage'), seconds=time.time() - t0)


def run(args):
    release = json.loads((OUT / 'release.json').read_text(encoding='utf-8'))
    states = release['states']
    check_prompts(states)
    rows_path = OUT / f'rows_{args.model}.jsonl'
    done = set()
    if rows_path.exists():
        for line in rows_path.read_text(encoding='utf-8').splitlines():
            r = json.loads(line); done.add((r['state_id'], r['horizon']))
    todo = [(s, h) for s in states for h in HORIZONS if (s['state_id'], h) not in done]
    if args.limit:
        todo = todo[:args.limit]
    base = f'http://localhost:{args.port}'
    print(f'{len(todo)} queries to run, {len(done)} already done', flush=True)

    def one(item):
        s, h = item
        try:
            r = query(base, args.model, s['fen'], h, args.max_tokens, args.timeout)
            move = parse_move(r['content'], s['fen'])
            return dict(state_id=s['state_id'], horizon=h, move=move, truncated=r['finish_reason'] == 'length',
                        failure=None, **r)
        except Exception as e:  # recorded, never retried
            return dict(state_id=s['state_id'], horizon=h, move=None, truncated=False, failure=repr(e)[:300])

    with open(rows_path, 'a', encoding='utf-8') as fh, cf.ThreadPoolExecutor(args.concurrency) as ex:
        for i, row in enumerate(ex.map(one, todo), 1):
            fh.write(json.dumps(row) + '\n'); fh.flush()
            if i % 20 == 0 or i == len(todo):
                print(json.dumps(dict(done=i, total=len(todo), move=row['move'], trunc=row['truncated'],
                                      fail=row['failure'] is not None)), flush=True)


# ---------------------------------------------------------------- analysis
def eq(orc, move):
    if move is None or move not in orc['action_values']:
        return 0.0
    span = orc['best_value'] - orc['worst_value']
    return 1.0 if span == 0 else (orc['action_values'][move] - orc['worst_value']) / span


def boot_ci(xs, seed, reps=10000, alpha=0.025):
    rng = random.Random(seed); n = len(xs)
    ms = sorted(sum(xs[rng.randrange(n)] for _ in range(n)) / n for _ in range(reps))
    return [ms[int(alpha / 2 * reps)], ms[int((1 - alpha / 2) * reps) - 1]]


def boot_diff(a, b, seed, reps=10000, alpha=0.025):
    rng = random.Random(seed)
    ds = sorted(sum(a[rng.randrange(len(a))] for _ in a) / len(a) - sum(b[rng.randrange(len(b))] for _ in b) / len(b)
                for _ in range(reps))
    lo, hi = ds[int(alpha / 2 * reps)], ds[int((1 - alpha / 2) * reps) - 1]
    est = sum(a) / len(a) - sum(b) / len(b)
    p = 2 * min(sum(d <= 0 for d in ds), sum(d >= 0 for d in ds)) / reps
    return est, [lo, hi], min(1.0, p)


def mcnemar(b, c):
    n = b + c
    return 1.0 if n == 0 else min(1.0, 2 * sum(math.comb(n, i) for i in range(min(b, c) + 1)) / 2 ** n)


def analyze(args):
    release = json.loads((OUT / 'release.json').read_text(encoding='utf-8'))
    by_id = {s['state_id']: s for s in release['states']}
    rows = {}
    for line in (OUT / f'rows_{args.model}.jsonl').read_text(encoding='utf-8').splitlines():
        r = json.loads(line); rows[(r['state_id'], r['horizon'])] = r
    H = HORIZONS[-1]
    n_q = len(rows); trunc = sum(r['truncated'] for r in rows.values())
    fail = sum(r['failure'] is not None for r in rows.values())
    illegal = sum(r['move'] is None for r in rows.values())
    g = {True: [], False: []}; use = [0, 0, 0]; b8 = c8 = 0
    churn = {True: dict(found=0, lost=0), False: dict(found=0, lost=0)}
    h1_best_sens = []; changed = 0
    for sid, s in by_id.items():
        if (sid, 1) not in rows or (sid, H) not in rows:
            continue
        a1, aH = rows[(sid, 1)]['move'], rows[(sid, H)]['move']
        oH, o1 = s['oracles'][str(H)], s['oracles']['1']
        sens = s['sensitive']
        g[sens].append(eq(oH, aH) - eq(oH, a1))
        changed += a1 != aH
        bH, b1 = aH in oH['optimal_actions'], a1 in oH['optimal_actions']
        churn[sens]['found'] += bH and not b1; churn[sens]['lost'] += b1 and not bH
        if sens:
            use[0] += bH; use[1] += b1; use[2] += 1
            b8 += bH and not b1; c8 += b1 and not bH
            h1_best_sens.append(1.0 if a1 in o1['optimal_actions'] else 0.0)
    rnd = {k: sum(len(set(s['oracles'][k]['optimal_actions'])) / len(s['oracles'][k]['action_values'])
                  for s in by_id.values() if s['sensitive']) / sum(s['sensitive'] for s in by_id.values())
           for k in ('1', str(H))}
    est, ci, p = boot_diff(g[True], g[False], 20261008)
    out = dict(model=args.model, queries=n_q, truncation_rate=trunc / max(n_q, 1), failures=fail, unparsed_or_illegal=illegal,
               answers_changed=changed / max(len(g[True]) + len(g[False]), 1),
               primary=dict(estimate=est, ci_975=ci, p=p),
               sensitive_gain=dict(mean=sum(g[True]) / len(g[True]), ci_975=boot_ci(g[True], 1)),
               control_gain=dict(mean=sum(g[False]) / len(g[False]), ci_975=boot_ci(g[False], 2)),
               use_at_H=use[0] / use[2], h_blind_baseline=use[1] / use[2], mcnemar_p=mcnemar(b8, c8),
               h1_best_rate_on_sensitive=sum(h1_best_sens) / len(h1_best_sens),
               random_best_rate_on_sensitive=rnd, churn={'sensitive': churn[True], 'control': churn[False]},
               n_sensitive=len(g[True]), n_control=len(g[False]))
    path = OUT / f'analysis_{args.model}.json'
    path.write_text(json.dumps(out, indent=1), encoding='utf-8')
    print(json.dumps(out, indent=1))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('action', choices=('build', 'run', 'analyze'))
    ap.add_argument('--seed', type=int, default=20261008)
    ap.add_argument('--candidates', type=int, default=1200)
    ap.add_argument('--per-set', type=int, default=120)
    ap.add_argument('--workers', type=int, default=8)
    ap.add_argument('--model')
    ap.add_argument('--port', type=int, default=18900)
    ap.add_argument('--concurrency', type=int, default=8)
    ap.add_argument('--max-tokens', type=int, default=16000)
    ap.add_argument('--timeout', type=int, default=1800)
    ap.add_argument('--limit', type=int)
    args = ap.parse_args()
    {'build': build, 'run': run, 'analyze': analyze}[args.action](args)


if __name__ == '__main__':
    main()

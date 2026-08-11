from __future__ import annotations

from copy import deepcopy
import hashlib
import re
from typing import Any, Iterable, Sequence

from .game_cards import PLAYER_ID_RE
from .world import WorldObject, WorldStore


PSYCHE_CHESS_SCHEMA = "nexus-psyche-chess/1"
PSYCHE_CHESS_KIND = "standard_chess_with_untrusted_banter_channel"
PSYCHE_CHESS_TITLE = "NEXUS PSYCHE-OUT CHESS"
INITIAL_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
MAX_PSYCHE_CHARS = 512
FILES = "abcdefgh"
RANKS = "12345678"
UCI_RE = re.compile(r"^[a-h][1-8][a-h][1-8][qrbn]?$", re.ASCII)


def _claim_boundary() -> dict[str, bool]:
    return {
        "standard_chess_legality_runtime_owned": True,
        "psyche_text_is_untrusted_banter": True,
        "psyche_text_is_system_instruction": False,
        "psyche_text_is_evidence": False,
        "psyche_text_changes_authority": False,
        "baseketball_dialogue_or_branding_reproduced": False,
        "progression_creates_authority": False,
    }


def psyche_chess_catalog() -> dict[str, Any]:
    return {
        "schema": PSYCHE_CHESS_SCHEMA,
        "title": PSYCHE_CHESS_TITLE,
        "game_kind": PSYCHE_CHESS_KIND,
        "move_notation": "UCI",
        "psyche_max_chars": MAX_PSYCHE_CHARS,
        "claim_boundary": _claim_boundary(),
    }


def _square(file_index: int, rank_index: int) -> str:
    return FILES[file_index] + RANKS[rank_index]


def _coord(square: str) -> tuple[int, int]:
    return FILES.index(square[0]), RANKS.index(square[1])


def _color(piece: str) -> str:
    return "w" if piece.isupper() else "b"


def _enemy(color: str) -> str:
    return "b" if color == "w" else "w"


def _parse_fen(fen: str) -> dict[str, Any]:
    if not isinstance(fen, str):
        raise ValueError("chess FEN must be text")
    parts = fen.split()
    if len(parts) != 6:
        raise ValueError("chess FEN must contain six fields")
    placement, turn, castling, ep, halfmove_raw, fullmove_raw = parts
    if turn not in {"w", "b"}:
        raise ValueError("chess FEN turn is invalid")
    if castling != "-" and (any(ch not in "KQkq" for ch in castling) or len(set(castling)) != len(castling)):
        raise ValueError("chess FEN castling rights are invalid")
    ordered_castling = "".join(ch for ch in "KQkq" if ch in castling)
    if castling != "-" and castling != ordered_castling:
        raise ValueError("chess FEN castling rights are not canonical")
    if ep != "-" and (len(ep) != 2 or ep[0] not in FILES or ep[1] not in {"3", "6"}):
        raise ValueError("chess FEN en-passant square is invalid")
    try:
        halfmove = int(halfmove_raw)
        fullmove = int(fullmove_raw)
    except ValueError as exc:
        raise ValueError("chess FEN counters are invalid") from exc
    if halfmove < 0 or fullmove < 1:
        raise ValueError("chess FEN counters are invalid")
    ranks = placement.split("/")
    if len(ranks) != 8:
        raise ValueError("chess FEN board must contain eight ranks")
    board: dict[str, str] = {}
    for fen_rank_index, rank_text in enumerate(ranks):
        rank = 7 - fen_rank_index
        file_index = 0
        for token in rank_text:
            if token.isdigit():
                amount = int(token)
                if not 1 <= amount <= 8:
                    raise ValueError("chess FEN empty-square count is invalid")
                file_index += amount
            elif token in "PNBRQKpnbrqk":
                if file_index >= 8:
                    raise ValueError("chess FEN rank overflows")
                board[_square(file_index, rank)] = token
                file_index += 1
            else:
                raise ValueError("chess FEN contains an invalid piece")
        if file_index != 8:
            raise ValueError("chess FEN rank does not contain eight files")
    if list(board.values()).count("K") != 1 or list(board.values()).count("k") != 1:
        raise ValueError("chess position must contain one king per side")
    return {
        "board": board,
        "turn": turn,
        "castling": "-" if castling == "-" else ordered_castling,
        "ep": None if ep == "-" else ep,
        "halfmove": halfmove,
        "fullmove": fullmove,
    }


def _fen(position: dict[str, Any]) -> str:
    board = position["board"]
    rank_texts: list[str] = []
    for rank in range(7, -1, -1):
        empty = 0
        parts: list[str] = []
        for file_index in range(8):
            piece = board.get(_square(file_index, rank))
            if piece is None:
                empty += 1
            else:
                if empty:
                    parts.append(str(empty))
                    empty = 0
                parts.append(piece)
        if empty:
            parts.append(str(empty))
        rank_texts.append("".join(parts))
    castling = position["castling"] if position["castling"] else "-"
    ep = position["ep"] if position["ep"] is not None else "-"
    return f"{'/'.join(rank_texts)} {position['turn']} {castling} {ep} {position['halfmove']} {position['fullmove']}"


def _king_square(board: dict[str, str], color: str) -> str:
    target = "K" if color == "w" else "k"
    for square, piece in board.items():
        if piece == target:
            return square
    raise ValueError("chess king is missing")


def _attacked(board: dict[str, str], target: str, by_color: str) -> bool:
    tx, ty = _coord(target)
    pawn = "P" if by_color == "w" else "p"
    pawn_source_rank = ty - 1 if by_color == "w" else ty + 1
    for dx in (-1, 1):
        x = tx - dx
        if 0 <= x < 8 and 0 <= pawn_source_rank < 8 and board.get(_square(x, pawn_source_rank)) == pawn:
            return True
    knight = "N" if by_color == "w" else "n"
    for dx, dy in ((1, 2), (2, 1), (-1, 2), (-2, 1), (1, -2), (2, -1), (-1, -2), (-2, -1)):
        x, y = tx + dx, ty + dy
        if 0 <= x < 8 and 0 <= y < 8 and board.get(_square(x, y)) == knight:
            return True
    king = "K" if by_color == "w" else "k"
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            if dx == dy == 0:
                continue
            x, y = tx + dx, ty + dy
            if 0 <= x < 8 and 0 <= y < 8 and board.get(_square(x, y)) == king:
                return True
    slider_sets = (
        (((1, 0), (-1, 0), (0, 1), (0, -1)), {"R", "Q"} if by_color == "w" else {"r", "q"}),
        (((1, 1), (1, -1), (-1, 1), (-1, -1)), {"B", "Q"} if by_color == "w" else {"b", "q"}),
    )
    for directions, pieces in slider_sets:
        for dx, dy in directions:
            x, y = tx + dx, ty + dy
            while 0 <= x < 8 and 0 <= y < 8:
                piece = board.get(_square(x, y))
                if piece is not None:
                    if piece in pieces:
                        return True
                    break
                x += dx
                y += dy
    return False


def _in_check(position: dict[str, Any], color: str) -> bool:
    return _attacked(position["board"], _king_square(position["board"], color), _enemy(color))


def _ray_moves(board: dict[str, str], source: str, color: str, directions: Iterable[tuple[int, int]]) -> list[tuple[str, str, str | None]]:
    sx, sy = _coord(source)
    result: list[tuple[str, str, str | None]] = []
    for dx, dy in directions:
        x, y = sx + dx, sy + dy
        while 0 <= x < 8 and 0 <= y < 8:
            target = _square(x, y)
            occupant = board.get(target)
            if occupant is None:
                result.append((source, target, None))
            else:
                if _color(occupant) != color:
                    result.append((source, target, None))
                break
            x += dx
            y += dy
    return result


def _pseudo_moves(position: dict[str, Any], color: str) -> list[tuple[str, str, str | None]]:
    board = position["board"]
    moves: list[tuple[str, str, str | None]] = []
    for source, piece in sorted(board.items()):
        if _color(piece) != color:
            continue
        sx, sy = _coord(source)
        kind = piece.upper()
        if kind == "P":
            direction = 1 if color == "w" else -1
            start_rank = 1 if color == "w" else 6
            promotion_rank = 7 if color == "w" else 0
            one_y = sy + direction
            if 0 <= one_y < 8:
                one = _square(sx, one_y)
                if one not in board:
                    if one_y == promotion_rank:
                        for promotion in "qrbn":
                            moves.append((source, one, promotion))
                    else:
                        moves.append((source, one, None))
                        two_y = sy + 2 * direction
                        two = _square(sx, two_y)
                        if sy == start_rank and two not in board:
                            moves.append((source, two, None))
            for dx in (-1, 1):
                x, y = sx + dx, sy + direction
                if not (0 <= x < 8 and 0 <= y < 8):
                    continue
                target = _square(x, y)
                occupant = board.get(target)
                if (occupant is not None and _color(occupant) != color) or target == position["ep"]:
                    if y == promotion_rank:
                        for promotion in "qrbn":
                            moves.append((source, target, promotion))
                    else:
                        moves.append((source, target, None))
        elif kind == "N":
            for dx, dy in ((1, 2), (2, 1), (-1, 2), (-2, 1), (1, -2), (2, -1), (-1, -2), (-2, -1)):
                x, y = sx + dx, sy + dy
                if 0 <= x < 8 and 0 <= y < 8:
                    target = _square(x, y)
                    occupant = board.get(target)
                    if occupant is None or _color(occupant) != color:
                        moves.append((source, target, None))
        elif kind == "B":
            moves.extend(_ray_moves(board, source, color, ((1, 1), (1, -1), (-1, 1), (-1, -1))))
        elif kind == "R":
            moves.extend(_ray_moves(board, source, color, ((1, 0), (-1, 0), (0, 1), (0, -1))))
        elif kind == "Q":
            moves.extend(_ray_moves(board, source, color, ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1))))
        elif kind == "K":
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    if dx == dy == 0:
                        continue
                    x, y = sx + dx, sy + dy
                    if 0 <= x < 8 and 0 <= y < 8:
                        target = _square(x, y)
                        occupant = board.get(target)
                        if occupant is None or _color(occupant) != color:
                            moves.append((source, target, None))
            if not _in_check(position, color):
                if color == "w" and source == "e1":
                    if "K" in position["castling"] and board.get("h1") == "R" and all(square not in board for square in ("f1", "g1")) and not _attacked(board, "f1", "b") and not _attacked(board, "g1", "b"):
                        moves.append(("e1", "g1", None))
                    if "Q" in position["castling"] and board.get("a1") == "R" and all(square not in board for square in ("b1", "c1", "d1")) and not _attacked(board, "d1", "b") and not _attacked(board, "c1", "b"):
                        moves.append(("e1", "c1", None))
                if color == "b" and source == "e8":
                    if "k" in position["castling"] and board.get("h8") == "r" and all(square not in board for square in ("f8", "g8")) and not _attacked(board, "f8", "w") and not _attacked(board, "g8", "w"):
                        moves.append(("e8", "g8", None))
                    if "q" in position["castling"] and board.get("a8") == "r" and all(square not in board for square in ("b8", "c8", "d8")) and not _attacked(board, "d8", "w") and not _attacked(board, "c8", "w"):
                        moves.append(("e8", "c8", None))
    return moves


def _apply_unchecked(position: dict[str, Any], move: tuple[str, str, str | None]) -> dict[str, Any]:
    source, target, promotion = move
    result = {
        "board": dict(position["board"]),
        "turn": _enemy(position["turn"]),
        "castling": position["castling"],
        "ep": None,
        "halfmove": position["halfmove"],
        "fullmove": position["fullmove"] + (1 if position["turn"] == "b" else 0),
    }
    board = result["board"]
    piece = board.pop(source)
    captured = board.get(target)
    is_pawn = piece.upper() == "P"
    if is_pawn and target == position["ep"] and captured is None and source[0] != target[0]:
        tx, ty = _coord(target)
        captured_square = _square(tx, ty - 1 if _color(piece) == "w" else ty + 1)
        captured = board.pop(captured_square, None)
    if piece.upper() == "K" and abs(FILES.index(source[0]) - FILES.index(target[0])) == 2:
        if target == "g1":
            board["f1"] = board.pop("h1")
        elif target == "c1":
            board["d1"] = board.pop("a1")
        elif target == "g8":
            board["f8"] = board.pop("h8")
        elif target == "c8":
            board["d8"] = board.pop("a8")
    if promotion is not None:
        piece = promotion.upper() if _color(piece) == "w" else promotion.lower()
    board[target] = piece
    rights = set(position["castling"] if position["castling"] != "-" else "")
    if source == "e1" or piece == "K":
        rights.discard("K"); rights.discard("Q")
    if source == "e8" or piece == "k":
        rights.discard("k"); rights.discard("q")
    for rook_square, right in (("h1", "K"), ("a1", "Q"), ("h8", "k"), ("a8", "q")):
        if source == rook_square or target == rook_square:
            rights.discard(right)
    result["castling"] = "".join(ch for ch in "KQkq" if ch in rights) or "-"
    sx, sy = _coord(source)
    tx, ty = _coord(target)
    if is_pawn and abs(ty - sy) == 2:
        result["ep"] = _square(sx, (sy + ty) // 2)
    result["halfmove"] = 0 if is_pawn or captured is not None else position["halfmove"] + 1
    return result


def legal_moves_for_fen(fen: str) -> list[str]:
    position = _parse_fen(fen)
    color = position["turn"]
    legal: list[str] = []
    for move in _pseudo_moves(position, color):
        candidate = _apply_unchecked(position, move)
        if not _in_check(candidate, color):
            legal.append(move[0] + move[1] + (move[2] or ""))
    return sorted(legal)


def _insufficient_material(position: dict[str, Any]) -> bool:
    pieces = [(square, piece) for square, piece in position["board"].items() if piece.upper() != "K"]
    if not pieces:
        return True
    if len(pieces) == 1 and pieces[0][1].upper() in {"B", "N"}:
        return True
    if pieces and all(piece.upper() == "B" for _, piece in pieces):
        colors = {(FILES.index(square[0]) + RANKS.index(square[1])) % 2 for square, _ in pieces}
        return len(colors) == 1
    return False


def _position_status(fen: str) -> tuple[bool, str | None, str | None]:
    position = _parse_fen(fen)
    legal = legal_moves_for_fen(fen)
    if not legal:
        if _in_check(position, position["turn"]):
            winner = "b" if position["turn"] == "w" else "w"
            return True, "checkmate", winner
        return True, "stalemate", None
    if position["halfmove"] >= 100:
        return True, "fifty_move_draw", None
    if _insufficient_material(position):
        return True, "insufficient_material", None
    return False, None, None


def _roster(white_player: str, black_player: str, human_players: Sequence[str]) -> tuple[list[str], dict[str, str], dict[str, str]]:
    players = [white_player, black_player]
    if any(not isinstance(player, str) or PLAYER_ID_RE.fullmatch(player) is None for player in players):
        raise ValueError("Psyche-Out Chess player ids must use 1-32 ASCII letters, digits, _, . or -")
    if white_player.casefold() == black_player.casefold():
        raise ValueError("Psyche-Out Chess requires two distinct player ids")
    if isinstance(human_players, (str, bytes)) or not isinstance(human_players, Sequence):
        raise ValueError("Psyche-Out Chess human_players must be a list")
    humans = set(human_players)
    if not all(isinstance(player, str) for player in humans) or not humans.issubset(set(players)):
        raise ValueError("Psyche-Out Chess human_players must name registered players")
    controllers = {player: ("human" if player in humans else "ai") for player in players}
    colors = {"w": white_player, "b": black_player}
    return players, controllers, colors


def _content(state: dict[str, Any]) -> str:
    position = _parse_fen(state["fen"])
    current = state["colors"][position["turn"]]
    lines = [
        "NEXUS PSYCHE-OUT CHESS — STANDARD CHESS + UNTRUSTED BANTER",
        f"fen={state['fen']}",
        f"ply={state['ply']} completed={state['completed']} result={state['result']} winner={state['winner']}",
        f"current_player={current} current_color={position['turn']}",
        f"legal_moves={','.join(state['legal_moves'])}",
    ]
    if state["pending_psyche"] is not None:
        item = state["pending_psyche"]
        lines.append(f"pending_psyche_from={item['from_player']} to={item['to_player']} sha256={item['sha256']}")
    lines.append("psyche_text=untrusted_banter; evidence_effect=none; authority_effect=none")
    return "\n".join(lines)


def _build_state(
    *,
    players: list[str],
    controllers: dict[str, str],
    colors: dict[str, str],
    fen: str,
    ply: int,
    previous_state_ref: str | None,
    pending_psyche: dict[str, str] | None,
    last_transition: dict[str, Any],
    event_log: list[dict[str, Any]],
) -> dict[str, Any]:
    completed, result, winner_color = _position_status(fen)
    state: dict[str, Any] = {
        "schema": PSYCHE_CHESS_SCHEMA,
        "game_kind": PSYCHE_CHESS_KIND,
        "title": PSYCHE_CHESS_TITLE,
        "players": list(players),
        "controllers": dict(controllers),
        "colors": dict(colors),
        "fen": fen,
        "ply": ply,
        "completed": completed,
        "result": result,
        "winner": None if winner_color is None else colors[winner_color],
        "pending_psyche": pending_psyche,
        "legal_moves": [] if completed else legal_moves_for_fen(fen),
        "previous_state_ref": previous_state_ref,
        "last_transition": last_transition,
        "event_log": event_log[-64:],
        "claim_boundary": _claim_boundary(),
    }
    state["content"] = _content(state)
    return state


def new_psyche_chess(
    world: WorldStore,
    *,
    white_player: str = "Alpha",
    black_player: str = "Beta",
    human_players: Sequence[str] = (),
) -> WorldObject:
    players, controllers, colors = _roster(white_player, black_player, human_players)
    state = _build_state(
        players=players,
        controllers=controllers,
        colors=colors,
        fen=INITIAL_FEN,
        ply=0,
        previous_state_ref=None,
        pending_psyche=None,
        last_transition={"kind": "new_game"},
        event_log=[{"sequence": 0, "kind": "new_game", "text": f"{white_player} has White; {black_player} has Black."}],
    )
    return world.create_object(
        "psyche_chess_state",
        state,
        {"actor": "nexus_game_engine", "reason": "new_psyche_chess_game"},
    )


def _validate(state: dict[str, Any]) -> None:
    if state.get("schema") != PSYCHE_CHESS_SCHEMA or state.get("game_kind") != PSYCHE_CHESS_KIND:
        raise ValueError("unsupported Psyche-Out Chess state schema")
    players = state.get("players")
    colors = state.get("colors")
    controllers = state.get("controllers")
    if not isinstance(players, list) or len(players) != 2 or not isinstance(colors, dict) or set(colors) != {"w", "b"}:
        raise ValueError("Psyche-Out Chess roster is invalid")
    checked_players, checked_controllers, checked_colors = _roster(colors["w"], colors["b"], [
        player for player, controller in controllers.items() if controller == "human"
    ] if isinstance(controllers, dict) else [])
    if players != checked_players or controllers != checked_controllers or colors != checked_colors:
        raise ValueError("Psyche-Out Chess controller/color state is invalid")
    fen = state.get("fen")
    position = _parse_fen(fen)
    if _fen(position) != fen:
        raise ValueError("Psyche-Out Chess FEN is not canonical")
    completed, result, winner_color = _position_status(fen)
    winner = None if winner_color is None else colors[winner_color]
    if state.get("completed") != completed or state.get("result") != result or state.get("winner") != winner:
        raise ValueError("Psyche-Out Chess completion state is invalid")
    legal = [] if completed else legal_moves_for_fen(fen)
    if state.get("legal_moves") != legal:
        raise ValueError("Psyche-Out Chess legal-move list is inconsistent")
    ply = state.get("ply")
    if type(ply) is not int or ply < 0:
        raise ValueError("Psyche-Out Chess ply counter is invalid")
    previous = state.get("previous_state_ref")
    if ply == 0 and previous is not None:
        raise ValueError("new Psyche-Out Chess state must not have a predecessor")
    if ply > 0 and previous is not None and not isinstance(previous, str):
        raise ValueError("Psyche-Out Chess predecessor ref is invalid")
    pending = state.get("pending_psyche")
    if pending is not None:
        if not isinstance(pending, dict) or set(pending) != {"from_player", "to_player", "text", "sha256"}:
            raise ValueError("Psyche-Out Chess pending psyche is invalid")
        if not isinstance(pending["text"], str) or not pending["text"].strip() or len(pending["text"]) > MAX_PSYCHE_CHARS:
            raise ValueError("Psyche-Out Chess psyche text is invalid")
        if hashlib.sha256(pending["text"].encode("utf-8")).hexdigest() != pending["sha256"]:
            raise ValueError("Psyche-Out Chess psyche hash is invalid")
        current = colors[position["turn"]]
        opponent = colors[_enemy(position["turn"])]
        if pending["to_player"] != current or pending["from_player"] != opponent:
            raise ValueError("Psyche-Out Chess psyche direction is invalid")
    log = state.get("event_log")
    if not isinstance(log, list) or not 1 <= len(log) <= 64:
        raise ValueError("Psyche-Out Chess event log is invalid")
    if state.get("claim_boundary") != _claim_boundary():
        raise ValueError("Psyche-Out Chess claim boundary is invalid")
    if state.get("content") != _content(state):
        raise ValueError("Psyche-Out Chess public content is inconsistent")


def inspect_psyche_chess(world: WorldStore, state_ref: str) -> WorldObject:
    obj = world.inspect(state_ref)
    if obj.object_type != "psyche_chess_state":
        raise ValueError("object is not a Psyche-Out Chess state")
    _validate(obj.payload)
    return obj


def add_psyche(world: WorldStore, state_ref: str, *, from_player: str, text: str) -> WorldObject:
    current = inspect_psyche_chess(world, state_ref)
    state = current.payload
    if state["completed"]:
        raise ValueError("Psyche-Out Chess is already complete")
    if state["pending_psyche"] is not None:
        raise ValueError("a psyche line is already pending for this turn")
    if not isinstance(text, str) or not text.strip() or len(text) > MAX_PSYCHE_CHARS:
        raise ValueError(f"psyche text must be 1-{MAX_PSYCHE_CHARS} characters")
    position = _parse_fen(state["fen"])
    current_player = state["colors"][position["turn"]]
    opponent = state["colors"][_enemy(position["turn"])]
    if from_player != opponent:
        raise ValueError("only the opponent of the side to move may deliver the psyche line")
    pending = {
        "from_player": from_player,
        "to_player": current_player,
        "text": text,
        "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
    }
    successor = _build_state(
        players=state["players"],
        controllers=state["controllers"],
        colors=state["colors"],
        fen=state["fen"],
        ply=state["ply"],
        previous_state_ref=current.object_id,
        pending_psyche=pending,
        last_transition={"kind": "psyche", "from_player": from_player, "to_player": current_player, "sha256": pending["sha256"]},
        event_log=state["event_log"] + [{"sequence": len(state["event_log"]), "kind": "psyche", "from_player": from_player, "to_player": current_player, "sha256": pending["sha256"]}],
    )
    return world.create_object(
        "psyche_chess_state",
        successor,
        {"actor": "nexus_game_engine", "reason": "psyche_chess_taunt"},
    )


def apply_psyche_chess_move(world: WorldStore, state_ref: str, *, player_id: str, move: str) -> WorldObject:
    current = inspect_psyche_chess(world, state_ref)
    state = current.payload
    if state["completed"]:
        raise ValueError("Psyche-Out Chess is already complete")
    if not isinstance(move, str) or UCI_RE.fullmatch(move) is None:
        raise ValueError("move must use bounded UCI notation")
    position = _parse_fen(state["fen"])
    current_player = state["colors"][position["turn"]]
    if player_id != current_player:
        raise ValueError("it is not that player's chess turn")
    if move not in state["legal_moves"]:
        raise ValueError("move is not legal in the current chess position")
    parsed = (move[:2], move[2:4], move[4] if len(move) == 5 else None)
    next_position = _apply_unchecked(position, parsed)
    next_fen = _fen(next_position)
    psyche = state["pending_psyche"]
    successor = _build_state(
        players=state["players"],
        controllers=state["controllers"],
        colors=state["colors"],
        fen=next_fen,
        ply=state["ply"] + 1,
        previous_state_ref=current.object_id,
        pending_psyche=None,
        last_transition={
            "kind": "move",
            "player_id": player_id,
            "move": move,
            "psyche_sha256": None if psyche is None else psyche["sha256"],
        },
        event_log=state["event_log"] + [{
            "sequence": len(state["event_log"]),
            "kind": "move",
            "player_id": player_id,
            "move": move,
            "psyche_sha256": None if psyche is None else psyche["sha256"],
        }],
    )
    return world.create_object(
        "psyche_chess_state",
        successor,
        {"actor": "nexus_game_engine", "reason": "psyche_chess_move"},
    )


def extract_legal_uci(text: str, legal_moves: Sequence[str]) -> str:
    if not isinstance(text, str):
        raise ValueError("AI chess move response must be text")
    tokens = re.findall(r"[a-h][1-8][a-h][1-8][qrbn]?", text.lower())
    matches = [token for token in tokens if token in legal_moves]
    unique = list(dict.fromkeys(matches))
    if len(unique) != 1:
        raise ValueError("AI chess move response must contain exactly one legal UCI move")
    return unique[0]


__all__ = [
    "INITIAL_FEN",
    "MAX_PSYCHE_CHARS",
    "PSYCHE_CHESS_KIND",
    "PSYCHE_CHESS_SCHEMA",
    "PSYCHE_CHESS_TITLE",
    "add_psyche",
    "apply_psyche_chess_move",
    "extract_legal_uci",
    "inspect_psyche_chess",
    "legal_moves_for_fen",
    "new_psyche_chess",
    "psyche_chess_catalog",
]

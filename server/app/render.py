from __future__ import annotations

from io import BytesIO

from PIL import Image, ImageDraw, ImageFont

from .engine import (
    Card,
    GameState,
    SUIT_NAMES,
    SUIT_SYMBOLS,
    actors,
    cards_to_codes,
    legal_actions,
)


def _font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    names = ["Arial Bold.ttf", "Arial.ttf"] if bold else ["Arial.ttf", "Helvetica.ttf"]
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def card_label(card: Card | None) -> str:
    if not card:
        return ""
    return f"{card.rank}{SUIT_SYMBOLS.get(card.suit, card.suit)}"


def suit_color(card: Card | None) -> str:
    if card and card.suit in ("H", "D"):
        return "#b9312d"
    return "#24201b"


def actor_summary(state: GameState) -> str:
    active = actors(state)
    if state.result == "durak":
        return f"Game finished: {state.names.get(state.durak or '', state.durak or '')} is durak"
    if state.result == "no_durak":
        return "Game finished: no durak"
    if not active:
        return "Waiting"
    return "Can act: " + ", ".join(state.names.get(player, player) for player in active)


def render_board_text(state: GameState, viewer: str) -> str:
    player = viewer if viewer in state.players else None
    hand = cards_to_codes(state.hands[player]) if player else []
    actions = legal_actions(state, player) if player else []
    bout = state.bout

    lines = [
        f"Game: {state.id}",
        f"Version: {state.version}",
        f"Status: {'finished' if state.result else 'active'}",
        f"Viewer: {viewer}",
        f"Players: {', '.join(f'{p}={state.names[p]}' for p in state.players)}",
        f"Trump: {SUIT_NAMES.get(state.trump_suit, state.trump_suit)} ({SUIT_SYMBOLS.get(state.trump_suit, state.trump_suit)})",
        f"Visible trump card: {card_label(state.trump_card) or 'none'}",
        f"Draw pile: {len(state.stock)}",
        f"Discard: {len(state.discard)}",
        f"Finished: {', '.join(state.finished) or 'none'}",
        f"Result: {state.result or 'none'}",
        f"Durak: {state.durak or 'none'}",
        f"{actor_summary(state)}",
        "",
        "Card counts:",
        *(f"- {player_id}: {len(state.hands[player_id])}" for player_id in state.players),
        "",
    ]

    if bout:
        lines.extend(
            [
                f"Bout attacker: {bout.attacker} ({state.names[bout.attacker]})",
                f"Bout defender: {bout.defender} ({state.names[bout.defender]})",
                f"Defender starting hand count: {bout.defender_hand_count}",
                f"Passed: {', '.join(bout.passed) or 'none'}",
                "Table:",
            ]
        )
        if not bout.table:
            lines.append("- empty")
        for pair in bout.table:
            defense = card_label(pair.defense) if pair.defense else "undefended"
            lines.append(f"- #{pair.id}: {pair.attacker} attacked {card_label(pair.attack)} -> {defense}")
        lines.append("")

    if player:
        lines.extend(["Your hand:", *(f"- {card}" for card in hand), ""])
    elif state.result:
        lines.extend(["Final hands:", *(f"- {p}: {', '.join(cards_to_codes(state.hands[p])) or 'empty'}" for p in state.players), ""])

    lines.extend(["Legal actions:", *(f"- {action}" for action in actions)])
    if not actions:
        lines.append("- none")

    lines.extend(["", "Recent public log:"])
    for item in state.history[-12:]:
        lines.append(f"- v{item.get('version', '?')}: {item.get('type')} {public_event_text(item)}")

    return "\n".join(lines)


def public_event_text(item: dict) -> str:
    parts = []
    for key in ("player", "attacker", "defender", "attackId", "card", "trumpSuit", "trumpCard"):
        if key in item and item[key] is not None:
            parts.append(f"{key}={item[key]}")
    return " ".join(parts)


def draw_card(draw: ImageDraw.ImageDraw, xy: tuple[int, int], card: Card | None, *, back: bool = False, scale: float = 1.0) -> None:
    x, y = xy
    w = int(70 * scale)
    h = int(100 * scale)
    radius = max(5, int(8 * scale))
    if back:
        draw.rounded_rectangle((x, y, x + w, y + h), radius=radius, fill="#7b2431", outline="#f5e6c9", width=2)
        draw.rounded_rectangle((x + 10, y + 10, x + w - 10, y + h - 10), radius=radius, outline="#d8b26a", width=2)
        return

    draw.rounded_rectangle((x, y, x + w, y + h), radius=radius, fill="#fff8ea", outline="#2d261f", width=2)
    if not card:
        return
    font = _font(int(24 * scale), bold=True)
    small = _font(int(16 * scale), bold=True)
    draw.text((x + 9 * scale, y + 7 * scale), card.rank, fill=suit_color(card), font=font)
    draw.text((x + 12 * scale, y + 37 * scale), SUIT_SYMBOLS.get(card.suit, card.suit), fill=suit_color(card), font=font)
    draw.text((x + w - 24 * scale, y + h - 28 * scale), SUIT_SYMBOLS.get(card.suit, card.suit), fill=suit_color(card), font=small)


def draw_waiting_card(draw: ImageDraw.ImageDraw, xy: tuple[int, int], *, scale: float = 1.0) -> None:
    x, y = xy
    w = int(70 * scale)
    h = int(100 * scale)
    radius = max(5, int(8 * scale))
    draw.rounded_rectangle((x, y, x + w, y + h), radius=radius, outline="#b7d4bd", width=3)
    draw.rounded_rectangle((x + 4, y + 4, x + w - 4, y + h - 4), radius=radius, outline="#b7d4bd", width=1)


def hand_layout(card_count: int) -> tuple[int, float, int, int]:
    if card_count <= 12:
        return 12, 1.0, 100, 0
    if card_count <= 24:
        return 12, 0.72, 100, 78
    if card_count <= 36:
        return 12, 0.55, 96, 58
    return 13, 0.42, 92, 44


def render_board_png(state: GameState, viewer: str) -> bytes:
    player = viewer if viewer in state.players else None
    image = Image.new("RGB", (1400, 900), "#18472f")
    draw = ImageDraw.Draw(image)
    title = _font(20, bold=True)
    label = _font(28, bold=True)
    medium = _font(20, bold=True)
    small = _font(16)
    tiny = _font(13)

    draw.rectangle((0, 0, 1400, 900), fill="#17442e")
    draw.rounded_rectangle((26, 24, 1374, 876), radius=30, fill="#1d5b3e", outline="#d0aa69", width=4)
    draw.text((54, 42), f"Durak · {state.id} · v{state.version} · viewer {viewer}", fill="#fff3d8", font=title)
    draw.text((54, 70), actor_summary(state), fill="#d7e8d6", font=small)

    active = set(actors(state))
    seat_w = 200
    for index, seat in enumerate(state.players[:6]):
        x = 54 + index * (seat_w + 10)
        y = 108
        fill = "#f1d38e" if seat in active else "#e7f1dc"
        if seat == player:
            fill = "#ffe3a0"
        draw.rounded_rectangle((x, y, x + seat_w, y + 70), radius=10, fill=fill, outline="#2b271f", width=2)
        draw.text((x + 12, y + 10), f"{seat.upper()} {state.names[seat][:14]}", fill="#221e19", font=medium)
        draw.text((x + 12, y + 42), f"{len(state.hands[seat])} cards{' · you' if seat == player else ''}", fill="#4e463a", font=small)

    draw.rounded_rectangle((1095, 42, 1332, 178), radius=16, fill="#144d33", outline="#7c8d65", width=2)
    draw.text((1116, 62), "Trump", fill="#fff3d8", font=medium)
    draw.text((1198, 54), SUIT_SYMBOLS.get(state.trump_suit, state.trump_suit), fill="#fff3d8", font=_font(58, bold=True))
    draw.text((1116, 104), f"{SUIT_NAMES[state.trump_suit]} · draw {len(state.stock)} · discard {len(state.discard)}", fill="#d7e8d6", font=small)
    if state.trump_card:
        draw_card(draw, (1270, 58), state.trump_card, scale=0.62)

    draw.rounded_rectangle((300, 210, 1100, 610), radius=20, fill="#236845", outline="#a67e46", width=4)
    table_title = "Table"
    if state.bout:
        table_title = f"{state.bout.attacker.upper()} attacks {state.bout.defender.upper()}"
    draw.text((330, 232), table_title, fill="#fff3d8", font=label)

    if state.bout and state.bout.table:
        table_count = len(state.bout.table)
        table_scale = 1.4 if table_count <= 2 else 1.15
        start_x = 440 if table_count == 1 else 350
        gap_x = 300 if table_count <= 2 else 235
        for idx, pair in enumerate(state.bout.table[:6]):
            x = start_x + (idx % 3) * gap_x
            y = 292 + (idx // 3) * 150
            draw.text((x, y - 22), f"#{pair.id}", fill="#f2d797", font=small)
            draw_card(draw, (x + 28, y), pair.attack, scale=table_scale)
            if pair.defense:
                draw_card(draw, (x + 28 + int(52 * table_scale), y + int(20 * table_scale)), pair.defense, scale=table_scale)
            else:
                draw_waiting_card(draw, (x + 28 + int(22 * table_scale), y + int(12 * table_scale)), scale=table_scale)
            label_text = f"{pair.attacker.upper()}"
            if pair.defender:
                label_text += f" -> {pair.defender.upper()}"
            draw.text((x + 28, y + int(126 * table_scale)), label_text, fill="#d7e8d6", font=small)
    elif state.bout:
        draw.text((330, 300), "Waiting for opening attack.", fill="#d7e8d6", font=medium)
    else:
        draw.text((330, 300), "No active bout.", fill="#d7e8d6", font=medium)

    draw.rounded_rectangle((54, 630, 1346, 886), radius=18, fill="#184d35", outline="#7c8d65", width=2)
    hand_title = "Your hand" if player else "Hidden hands"
    if player:
        hand_title += f" · {len(state.hands[player])} cards"
    draw.text((78, 654), hand_title, fill="#fff3d8", font=label)
    if player:
        columns, scale, step_x, step_y = hand_layout(len(state.hands[player]))
        for index, card in enumerate(state.hands[player]):
            x = 78 + (index % columns) * step_x
            y = 704 + (index // columns) * step_y
            draw_card(draw, (x, y), card, scale=scale)
    elif state.result:
        draw.text((78, 724), "Game finished. Full replay is available in JSON.", fill="#d7e8d6", font=medium)
    else:
        for index in range(min(12, max((len(state.hands[p]) for p in state.players), default=0))):
            draw_card(draw, (78 + index * 58, 724), None, back=True, scale=0.72)

    out = BytesIO()
    image.save(out, format="PNG")
    return out.getvalue()

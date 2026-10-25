"""Первый опыт FretOpt с медиатором. Запуск: python3 pick_opt.py

Выбираем среди заданных аппликатур, не среди всех путей по грифу.
Цены правой руки — учебные предположения, не измерения сложности.
Рядом нужен прежний fretopt.py: его модель левой руки не меняется.
"""

import itertools
from fretopt import Position, solve_hand


# 1 — тонкая e, 6 — толстая E. D идёт от 6 к 1, U — от 1 к 6.
# Каждая пара — [струна, лад]. Оба варианта дают одинаковые MIDI-ноты.
layouts = [
    [[4, 7], [4, 9], [4, 10], [3, 7], [3, 9], [3, 10], [2, 8], [2, 10]],
    [[4, 7], [4, 9], [3, 5], [3, 7], [2, 5], [2, 6], [1, 3], [1, 5]],
]

# USX: выход из плоскости струн после U; DSX: после D; DBX: после обоих.
profile = "USX"
allow_sweep = False       # True разрешает D-D / U-U на соседних струнах по ходу удара.
first_stroke = None       # None — можно начать любым ударом; можно поставить "D" или "U".
right_weight = 1.0        # Насколько стоимость правой руки влияет на общий результат.

# УСЛОВНЫЕ цены для демонстрации. Это не секунды, миллиметры или вероятность ошибки.
string_move_price = 0.25
extra_escape_price = 5.0
sweep_price = 0.6


def melody_of(tab):
    open_strings = [64, 59, 55, 50, 45, 40]
    melody = []
    for string, fret in tab:
        melody.append(open_strings[string - 1] + fret)
    return melody


def left_hand_cost(tab):
    # Единственный мост к старому FretOpt: закрепляем струну и лад каждой ноты.
    constraints = []
    for string, fret in tab:
        constraints.append([Position(string, fret)])
    result = solve_hand(melody_of(tab), constraints=constraints)
    return result.cost


def picking_step(string1, string2, stroke1, stroke2, profile, allow_sweep):
    distance = abs(string2 - string1)

    if stroke1 == stroke2:
        # Продолжать D можно с 4-й на 3-ю; продолжать U — с 3-й на 4-ю.
        down_sweep = stroke1 == "D" and string2 == string1 - 1
        up_sweep = stroke1 == "U" and string2 == string1 + 1
        if allow_sweep and (down_sweep or up_sweep):
            return string_move_price + sweep_price, "свип на соседнюю струну"
        # Повторный удар с возвратом и свип через пропущенную струну здесь не моделируем.
        return float("inf"), "вне разрешённых техник"

    if distance == 0:
        return 0.0, "чередование на одной струне"

    cost = string_move_price * distance
    escaped = profile == "DBX"
    if profile == "USX" and stroke1 == "U":
        escaped = True
    if profile == "DSX" and stroke1 == "D":
        escaped = True

    if escaped:
        return cost, "смена струны после выхода медиатора"
    return cost + extra_escape_price, "условная цена дополнительного выхода"


def picking_cost(tab, strokes, profile, allow_sweep):
    total = 0.0
    for i in range(len(tab) - 1):
        cost, reason = picking_step(
            tab[i][0], tab[i + 1][0], strokes[i], strokes[i + 1], profile, allow_sweep
        )
        total = total + cost
    return total


def best_picking(tab, profile, allow_sweep, first_stroke=None):
    if profile not in ["USX", "DSX", "DBX"]:
        raise ValueError("Профиль должен быть USX, DSX или DBX")
    if first_stroke not in [None, "D", "U"]:
        raise ValueError("Первый удар: None, D или U")
    if not 1 <= len(tab) <= 16:
        raise ValueError("Для учебного полного перебора нужно от 1 до 16 нот")

    min_cost = float("inf")
    best_strokes = None
    # product уже есть в твоём real_thing.py; здесь он сочетает D и U.
    for strokes in itertools.product(["D", "U"], repeat=len(tab)):
        if first_stroke is not None and strokes[0] != first_stroke:
            continue
        cost = picking_cost(tab, strokes, profile, allow_sweep)
        if cost < min_cost:
            min_cost = cost
            best_strokes = strokes
    return best_strokes, min_cost


def compare_layouts(layouts, profile, allow_sweep, right_weight, first_stroke=None):
    if not layouts:
        raise ValueError("Нужна хотя бы одна аппликатура")
    if not 0 <= right_weight < float("inf"):
        raise ValueError("Вес правой руки должен быть конечным и неотрицательным")
    melody = None
    rows = []
    for tab in layouts:
        # Position проверяет допустимость номера струны и лада.
        for string, fret in tab:
            Position(string, fret)
        if melody is None:
            melody = melody_of(tab)
        if melody_of(tab) != melody:
            raise ValueError("Аппликатуры должны играть одни и те же ноты в одном порядке")
        strokes, right = best_picking(tab, profile, allow_sweep, first_stroke)
        left = left_hand_cost(tab)
        total = left + right_weight * right
        rows.append([tab, strokes, left, right, total])

    # При равной цене левой руки даём исходному методу лучший правый вариант.
    left_best = 0
    joint_best = 0
    for i in range(1, len(rows)):
        if rows[i][2] < rows[left_best][2]:
            left_best = i
        elif rows[i][2] == rows[left_best][2] and rows[i][3] < rows[left_best][3]:
            left_best = i
        if rows[i][4] < rows[joint_best][4]:
            joint_best = i
    return rows, left_best, joint_best


def show_results(rows, left_best, joint_best, profile, allow_sweep, right_weight):
    print("MIDI:", melody_of(rows[0][0]))
    print("Профиль:", profile, "Свип разрешён:", allow_sweep, "Вес правой:", right_weight)
    print("Все цены условные. Выбор только среди заданных аппликатур.\n")
    for i in range(len(rows)):
        tab, strokes, left, right, total = rows[i]
        print("Вариант", i + 1, ":", tab)
        print("Удары:", " ".join(strokes))
        print("Левая:", round(left, 3), "Правая:", round(right, 3), "Сумма:", round(total, 3))
    print("\nВыбор только по левой руке: вариант", left_best + 1)
    print("Выбор с учётом обеих рук: вариант", joint_best + 1)
    print("\nРазбор правой руки выбранного варианта:")
    tab, strokes, left, right, total = rows[joint_best]
    for i in range(len(tab) - 1):
        cost, reason = picking_step(
            tab[i][0], tab[i + 1][0], strokes[i], strokes[i + 1], profile, allow_sweep
        )
        print(i + 1, "->", i + 2, ":", reason, "| цена", cost)


# При обычном запуске выполняем пример; при импорте для проверки — нет.
if __name__ == "__main__":
    rows, left_best, joint_best = compare_layouts(
        layouts, profile, allow_sweep, right_weight, first_stroke
    )
    show_results(rows, left_best, joint_best, profile, allow_sweep, right_weight)

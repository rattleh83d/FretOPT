"""Reproduce comparisons, controlled examples and known model counterexamples."""
from dataclasses import asdict, replace
import json
from pathlib import Path

from fretopt import (CostConfig, HandModel, Position, diagnostics,
                     physical_fret_span_mm, solve_baseline, solve_greedy, solve_hand)
from run import render, serialize


def pinned(frets, string=1):
    ps = [Position(string, f) for f in frets]
    return [p.midi for p in ps], [(p,) for p in ps]


def main():
    root, cfg = Path(__file__).resolve().parent, CostConfig()
    cases = [
        ("Свободный выбор позиции", [64, 66, 69, 67, 64], None, cfg),
        ("Вторая мелодия", [52, 55, 59, 62, 64], None, cfg),
        ("Рабочая растяжка 12–15–17", *pinned([12, 15, 17]), cfg),
        ("Нисходящий участок", *pinned([14, 12, 10]), cfg),
        ("Первая нота не anchor", *pinned([12, 10, 14, 11]), cfg),
        ("Hard cutoff внизу грифа", *pinned([1, 6]), cfg),
        ("Открытая струна без бонуса", *pinned([12, 0, 12]), cfg),
        ("Greedy failure с одинаковым началом", *pinned([0, 2, 4], 6), replace(cfg, palm_grid_mm=50)),
        ("Короткий контекст", *pinned([12, 17]), cfg),
        ("Контрпример памяти span", *pinned([12, 17] + [14] * 8), cfg),
    ]
    report = ["# FretOpt v0.1 — воспроизводимые результаты", "",
              "Сгенерировано `python3 experiments.py`. Это синтетические последовательности, "
              "а не транскрипции названных в handoff песен. Сравнивать числа M0, M1 и M3 "
              "напрямую нельзя: у них разные единицы. M2 и M3 имеют одну функцию стоимости.", "",
              "Начальное положение свободно и бесплатно. Все числа — результаты модели с "
              "пробными весами, не измеренная трудность игры.", ""]
    payload = []
    for title, notes, constraints, config in cases:
        results = [solve_baseline(notes, m, config, constraints) for m in ("M0", "M1")]
        results += [solve_greedy(notes, config, constraints), solve_hand(notes, config, constraints)]
        payload.append(dict(case=title, notes=notes, config=asdict(config),
                            constraints=[[asdict(p) for p in layer] for layer in constraints] if constraints else None,
                            results=[serialize(r, config) for r in results]))
        report += [f"## {title}", "", f"MIDI: `{notes}`. " +
                   ("Позиции закреплены для изоляции механики руки." if constraints else "Все допустимые позиции доступны."), "",
                   "| Модель | Стоимость | Путь: струна/лад |", "|---|---:|---|"]
        for r in results:
            ps = [getattr(s, "played", s) for s in r.path]
            report.append(f"| {r.model} | {r.cost:.6f} | " + " → ".join(f"{p.string}/{p.fret}" for p in ps) + " |")
        report += ["", "```text", render(results[-1], config), "```", ""]
        if config.palm_grid_mm == 50:
            report += ["Для этого контролируемого примера сетка = 50 мм, начальный центр единственный: 0 мм. "
                       "Greedy выбирает центры 0→50→100; DP — 0→100→100. "
                       "Второй шаг DP дороже на 0,5, но устраняет следующую перестановку.", "",
                       "```text", render(results[-2], config), "```", ""]

    report += ["## Обнаруженные контрпримеры", "",
               "1. **Предпочтение верхних ладов.** На MIDI `[64,66,69,67,64]` M3 выбирает "
               "`6/24→5/21→5/24→5/22→6/24`. Сжатая геометрия вознаграждается, доступ у корпуса, "
               "тембр и постановка пальцев отсутствуют. Нельзя объявлять этот путь экспертно лучшим.", "",
               "2. **Память span.** На `12→17` DP сохраняет центр 365 мм. Добавление восьми нот "
               "на 14-м ладу меняет начало на 360→365 мм: платная перестановка сбрасывает историю. "
               "Оставшийся span 14–17 продолжает стоить денег на повторениях 14. Это демонстрирует "
               "недостаток состояния: использованный ранее диапазон не равен текущему раскрытию руки. "
               "Фиксированная цена пресекает дешёвое дробление движения, но не этот способ сброса истории.", "",
               "3. **Нет поперечной координаты ладони.** Переход с одной струны на другую без "
               "продольного движения может иметь нулевую цену reposition. Модель учитывает смену "
               "струны и string-span, но не способна различить сохранение опоры и её перенос. "
               "Lucretia-подобное экспертное различие пока не представимо.", "",
               "4. **Сетка создаёт дополнительные запреты.** Допустимый непрерывный центр может "
               "попасть между узлами сетки. Проверены все пары ладов 0–24:", ""]
    model = HandModel(cfg)
    gaps = []
    for a in range(25):
        for b in range(a + 1, 25):
            width = physical_fret_span_mm(a, b, cfg)
            if width <= cfg.hard_stretch_mm and not set(model.centres[a]) & set(model.centres[b]):
                gaps.append(dict(low=a, high=b, span_mm=width))
                report.append(f"- `{a}–{b}`: {width:.3f} мм < 85 мм, но общего центра сетки нет.")
    report += ["", "Чувствительность 12→15→17 к сетке:", "",
               "| Шаг, мм | Стоимость M3 | Центры ладони, мм |", "|---:|---:|---|"]
    sensitivity = []
    for grid in (2.5, 5, 10):
        c = replace(cfg, palm_grid_mm=grid)
        notes, constraints = pinned([12, 15, 17])
        r = solve_hand(notes, c, constraints)
        centres = [s.palm_ref_mm for s in r.path]
        sensitivity.append(dict(grid_mm=grid, cost=r.cost, palm_centres=centres))
        report.append(f"| {grid} | {r.cost:.6f} | {centres} |")
    report += ["", "## Следующий эксперимент", "",
               "Сначала проверить с гитарой, можно ли на `12→17→14→14…` снять растяжку без "
               "перестановки ладони. Если да, следующей модели нужно отдельное описание текущего "
               "раскрытия/освобождения руки, а не новая константа штрафа. Для сетки можно добавить "
               "середины допустимых диапазонов как кандидаты и сравнить с текущей дискретизацией. "
               "Высокие лады и перенос опоры требуют отдельных экспертных пар примеров.", ""]
    (root / "REPORT.md").write_text("\n".join(report))
    (root / "experiments.json").write_text(json.dumps(dict(cases=payload, grid_gaps=gaps, sensitivity=sensitivity), ensure_ascii=False, indent=2) + "\n")
    (root / "config.json").write_text(json.dumps(asdict(cfg), indent=2) + "\n")
    print(f"Saved {root / 'REPORT.md'} and experiments.json; {len(cases)} cases")


if __name__ == "__main__":
    main()

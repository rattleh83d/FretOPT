import itertools
melody_input = input("Введи MIDI-ноты через пробел: ")
notes_as_text = melody_input.split()
melody = []
all_positions = []
open_strings = [64, 59, 55, 50, 45, 40]

def validate(note):
    return 40 <= note <= 88


for note_text in notes_as_text:
    note = int(note_text)
    melody.append(note)
print(melody)

def validate(note):
    return 40 <= note <= 88


def find_note_positions(note):
    positions = []
    fret = 0
    string = 0


    for i in range(6):
        fret = note - open_strings[i]
        string = i + 1

        if 0 <= fret <= 24:
            positions.append([string, fret])


    return positions



for note in melody:
    positions = find_note_positions(note)
    all_positions.append(positions)
print(all_positions)

path=all_positions

def path_cost(path):
    total_cost=0
    for i in range(len(path)-1):            
        string_cost=abs(path[i][0]-path[i+1][0])
        fret_cost=abs(path[i][1]-path[i+1][1])
        cost=string_cost+fret_cost 
        total_cost=total_cost+cost
    return total_cost



all_possible_paths = list(itertools.product(*all_positions))
print(f"\nВсего возможных вариантов аппликатуры: {len(all_possible_paths)}")


min_cost = float('inf')


for i, path in enumerate(all_possible_paths):
    current_cost = path_cost(path)

    if current_cost < min_cost:
        min_cost = current_cost
        best_path = path


print("\n=== ЛУЧШИЙ РЕЗУЛЬТАТ ===")
print("Оптимальный путь:", list(best_path))
print("Минимальная стоимость:", min_cost)






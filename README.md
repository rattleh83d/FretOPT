# FretOPT

A personal project built out of curiosity: is there a mathematically justified "best" fingering pattern for guitar?

I combined nearly a decade of playing experience across acoustic, electric, and bass guitar with a bit of mathematical reasoning and some coding to explore the question. The goal is not to replace taste or feel, but to test whether a compact optimization model can generate playable, efficient fingerings from musical input alone.

> ## Development process and AI assistance

I developed the project’s core logic and structure, proposed using physical fretboard measurements to model movement, and defined the main modeling assumptions.

Development was iterative: I decided what the program should do next and described the intended behavior, then used AI to help correctly translate those decisions into Python. After each addition, I worked through the implementation until I understood how it worked and how it connected to the rest of the program before moving on. This made development a learning process as well as a way to build the tool.

AI contributed help with implementation, refactoring, pushing to github, and automated tests. The project reflects my ideas and design decisions, but I do not claim to have written every line of code independently.

## Main idea

The core idea behind FretOPT is simple:

- small finger movements are usually cheaper than large repositioning moves
- keeping the hand within a narrow fret range can reduce strain and effort
- fingering choices should account for both note selection and movement cost

In other words, the project tries to model the tradeoff between:

- choosing the most natural note
- choosing the most efficient hand movement
- keeping the result comfortable and playable in real life

## Real-world application

This project is motivated by practical guitar playing, not abstract theory alone. The model is meant to reflect how a guitarist actually moves while playing:

- how often do you shift hand position?
- does a small movement save more effort than a more "obvious" fingering?
- can a better route be found by optimizing the hand path, not just the notes?

The goal is to see whether these choices can be described with a usable cost function and whether the result is genuinely helpful in real playing situations.

Early use and feedback:
- used by the band "Валентин Прекрасный" for MIDI-derived melody-to-tablature workflows
- tried by peer guitarists to explore practical applicability
## Main version

Run `python run.py 64 66 69 67` with MIDI note numbers (40 to 88).
The program lists playable string/fret positions for each note and uses dynamic
programming to find the lowest-cost path. The default M0 cost is
`abs(next_string - string) + abs(next_fret - fret)`, based on the original
`real_thing.py` experiment. The search uses explicit loops rather than listing
every possible complete path. It does not read `.mid` files or assign fingers.

`python pick_opt.py` compares two fixed layouts with the same left-hand cost
and an additional picking cost. Picking weights are assumptions, not measurements.

## Optional experiments

Use `--model M1`, `--model M2`, `--model M3` or `--model all` to run the
more complex experimental models. M1 measures physical distance, M2 makes
greedy hand-position decisions, and M3 searches over hand-position states.
These AI-assisted experiments are retained for comparison; they are not needed
for the default version. Their scores use different units and should not be
compared directly. The hand model does not represent individual fingers or tempo,
and treats open strings using the same geometry as fretted notes.

Use `--json result.json` to export results, `--positions 1:0 1:2 1:5 1:3`
to pin positions, and `--config config.json` to configure the experimental models.



## Checks

Run `python -m unittest discover -v`. Tests compare dynamic programming with
exhaustive search on small examples and check invalid inputs and picking rules.
`real_thing.py` remains the original learning sandbox; `run.py` is the main entry.

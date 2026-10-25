# FretOPT

A personal project built out of curiosity: is there a mathematically justified "best" fingering pattern for guitar?

I combined nearly a decade of playing experience across acoustic, electric, and bass guitar with a bit of mathematical reasoning and some coding to explore the question. The goal is not to replace musical intuition, but to test whether movement cost and hand efficiency can be modeled and optimized.

> AI was used to help refactor code and write tests during the early stages of the project. Future development is being written by hand as I continue learning and improving my programming skills.

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

## Further development

This project is still evolving. I plan to keep refining and expanding it as I continue exploring the problem, because the field is broad and there is still plenty to test and improve.

## Important note about LaTeX in GitHub READMEs

GitHub's default Markdown renderer does not support LaTeX or MathJax in README files. That is why formulas may appear broken or as plain text when written with LaTeX syntax.

For example, this type of math will not render correctly in a standard GitHub README:

```tex
\[
\text{cost} = \sum_i w_i \cdot d_i
\]
```

If you want proper mathematical rendering, you need a math-enabled environment such as:

- GitHub Pages with MathJax
- a docs site built with MkDocs / Jekyll / Hugo
- a local Markdown viewer that supports LaTeX rendering

For a GitHub README, the safest approach is to keep formulas as plain text or to move them to a math-enabled page.

## Current status

- exploratory research project
- personal project with practical guitar focus
- still under active development

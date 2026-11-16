# Licence and acknowledgement

Every repo of Adam McCarthy's carries a licence from the day it is created, public or private (decided 2026-11-15; before that a
private repo waited until it, or anything built from it, went public). There are two, and one exception:

- **Code repos: MIT License with Acknowledgement** (SPDX identifier `LicenseRef-MIT-Acknowledgement`). It is the MIT licence plus
  one condition: anything built with the work must say so, visibly and in plain words, and must not imply endorsement. It is
  custom wording, so it is not OSI-approved; the repo says this in one line so nobody is surprised. This is the default.
- **Repos that are not just code: Creative Commons Attribution 4.0 International** (CC BY 4.0), the standard text unchanged
  below a short credit line. This covers decks, written studies, style guides and knowledge stores. A repo that mixes code and
  content takes the MIT licence if the code is the product, and CC BY if the content is. Register a CC BY repo in `repos.toml`
  with `licence = "cc-by"`; the audit then checks for the CC text instead of the MIT text.

- **Exception: Idiom itself** is all rights reserved, with no licence granted (`LICENSE` in the repository): it holds the
  private voice, working notes and rules, and only the manifest files leave it, inside published repositories under their licences.
  Register it as `licence = "restricted"`.
- **Templates:** `templates/LICENSE.tmpl` (MIT) and `templates/LICENSE-CC-BY.tmpl` (CC BY). Replace `{{YEAR}}` (year of first commit), `{{NAME}}` (the repo's name) and `{{URL}}`
  (its GitHub address). Do not reword the conditions.
- **README:** every repo ends with a "Licence and acknowledgement" section (plain heading, a few lines): the licence name, the
  exact acknowledgement line to use, and which parts carry other terms (data, vendored code).
- **`pyproject.toml`:** where a repo declares a licence, `license = { file = "LICENSE" }`; do not use the SPDX string, because older build
  backends reject it.
- **Third-party material keeps its own terms** and its own notice: source data (Sodir NLOD 2.0, Volve terms, Copernicus,
  EMODnet), vendored libraries (D3, fonts) and anything under `vendor/`. State them in the README, never relicense them.
- **Public READMEs carry a badge row** directly under the title, as documentation for publishing: workflow status for each
  workflow the repo has (GitHub's own `badge.svg`, for example CI or the Pages deploy), the Python version when `pyproject.toml`
  declares one, and the licence. Static badges use `img.shields.io` with `color=lightgrey`, so no colour judges the repo. A repo with
  no workflow shows the version and licence only; never add a workflow just to earn a badge. Private repos get no badge row,
  because it would show to nobody: the Operations Centre shows their health instead.
- **Published stories** carry the acknowledgement in their README and, where the framework supports it, in the appendix
  ("Basis of analysis") next to the sources.
- **A repo that builds on another** (Wildcat on SubScout and Relief) acknowledges what it uses in its own README and appendix.

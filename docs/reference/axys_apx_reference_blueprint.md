# AXYS / APX Reference Blueprint

Version 2.0

> This document defines the editorial standards for the Axys/APX Reference Repository.
> The repository exists to document **how Axys/APX actually work**.
> It is intended for both human readers and AI coding assistants (such as Codex).

---

# 1. Purpose

This repository is a permanent technical reference for SS&C Axys and SS&C APX.

Its purpose is to preserve factual, implementation-oriented knowledge about:

- system architecture
- accounting data
- IMEX
- REP
- reports
- file layouts
- data fields
- processing behavior
- version differences
- implementation quirks

The repository is **not**:

- a software project
- a product roadmap
- a portfolio accounting textbook
- an AI workflow guide

---

# 2. Editorial Principles

## Facts First

Document supported facts.

Never invent Axys or APX behavior.

Every important technical statement should be identified as:

- Verified
- High Confidence
- Medium Confidence
- Unknown

Unknown is acceptable.

Invented certainty is not.

---

## Separate Axys/APX

Whenever behavior differs, document each system independently.

Avoid generic statements such as "the system."

---

## Prefer Evidence

Prefer:

- vendor documentation
- IMEX exports
- REP reports
- production observations
- consultant documentation
- examples
- tables

over general explanations.

---

## Preserve Unknowns

If something cannot be verified, record it as Unknown rather than guessing.

---

# 3. Intended Audience

This repository is written for:

- software developers
- consultants
- investment operations
- performance analysts
- data engineers
- AI coding assistants

Assume the reader is technically proficient.

---

# 4. Repository Structure

The repository uses role-oriented files. Reader-facing chapters live under
`reference/` for the normal reader path. Research notes live under `evidence/`
so they remain available as provenance without competing with the chapters.

| File group | Role | Source-of-truth boundary |
|---|---|---|
| `README.md` | Folder navigation hub. | Explains the reader path and file roles. |
| `axys_apx_reference_blueprint.md` | Governing editorial specification. | Defines evidence standards, confidence labels, chapter structure, and repository workflow. |
| `reference/Chapter_*.md` | Reader-facing reference. | Supported conclusions, Unknowns, implementation cautions, and cross-topic navigation. |
| `evidence/Research_*.md` | Evidence archive. | Source notes, dated research history, provenance, and unresolved details. |
| `contracts/*.md` | Implementation aid. | Cross-cutting contracts, generated summaries, and demo/test guidance. |
| `contracts/*.yaml` | Machine-readable contract. | Structured validation and implementation inputs. |
| `contracts/templates/*.yaml` | Site contract examples. | Site-level source-data contract shapes; not guaranteed vendor schemas. |
| `axys_apx_common_core_export.md` | Starter export reference. | Common field shapes and candidate aliases for integration planning. |

If a chapter and contract conflict, treat that as a cleanup issue. Contracts
should summarize or operationalize chapter conclusions, not compete with them.
If a research file contains the clearest explanation of a topic, fold that
explanation into the relevant chapter and leave the research file as provenance.

```text
    README.md
    axys_apx_reference_blueprint.md
    axys_apx_common_core_export.md
    reference/Chapter_01_Overview.md
    reference/Chapter_02_Axys_Architecture.md
    reference/Chapter_03_APX_Architecture.md
    reference/Chapter_04_Security_Master.md
    reference/Chapter_05_Transactions.md
    reference/Chapter_06_Holdings.md
    reference/Chapter_07_Cash.md
    reference/Chapter_08_Pricing.md
    reference/Chapter_09_Corporate_Actions.md
    reference/Chapter_10_Performance.md
    reference/Chapter_11_Classifications.md
    reference/Chapter_12_Imex.md
    reference/Chapter_13_Rep.md
    reference/Chapter_14_Reports.md
    reference/Chapter_15_Data_Dictionary.md
    reference/Chapter_16_Glossary.md
    reference/Chapter_17_Multi_Currency.md
    evidence/Research_02_Axys_Architecture.md
    evidence/Research_03_APX_Architecture.md
    evidence/Research_04_Security_Master.md
    evidence/Research_05_Transactions.md
    evidence/Research_06_Holdings.md
    evidence/Research_07_Cash.md
    evidence/Research_08_Pricing.md
    evidence/Research_09_Corporate_Actions.md
    evidence/Research_10_Performance.md
    evidence/Research_11_Classifications.md
    evidence/Research_12_IMEX.md
    evidence/Research_13_REP.md
    evidence/Research_14_Reports.md
    evidence/Research_15_Data_Dictionary.md
    evidence/Research_16_Glossary.md
    evidence/Research_17_Multi_Currency.md
    evidence/Research_17A_Multi_Currency_Cash_Provenance.md
    contracts/demo_extract_availability.md
    contracts/transaction_semantics_matrix.md
    contracts/transaction_semantics_matrix.yaml
    contracts/templates/
```

---

# 5. Standard Chapter Template

Use only the sections that are applicable.

1. Overview
2. Axys
3. APX
4. IMEX
5. REP
6. Data Model
7. Common Fields
8. Examples
9. Known Issues / Quirks
10. References
11. Unknowns

---

# 6. Documentation Standards

Prefer:

- tables over prose
- field dictionaries
- sample IMEX exports
- sample REP reports
- diagrams
- examples
- version differences

Avoid:

- unnecessary portfolio accounting theory
- product ideas
- speculative implementation details
- unsupported conclusions

---

# 7. Field Dictionary Standard

| Field | Description | Axys | APX | IMEX | REP | Confidence |
|------|-------------|------|-----|------|-----|------------|

---

# 8. Success Criteria

A reader should be able to answer questions such as:

- Which IMEX object exports transactions?
- Which REP report contains security performance?
- Where are classifications stored?
- Does APX store or recalculate performance?
- Which fields identify a security?
- Which fields are required?
- Which reports use stored values?
- What are the known quirks?

using only this repository.

---

# 9. Repository Workflow

For each chapter:

1. Research the topic.
2. Save the evidence notes in `evidence/Research_*.md`.
3. Write or expand the reader-facing chapter in `reference/Chapter_*.md` using
   the evidence.
4. Update the relevant `contracts/` file only when the chapter conclusion has
   an implementation-facing demo, validation, or test implication.
5. Integrate additional verified information into the relevant subject section
   rather than appending dated update sections. Preserve chronology in the
   evidence file and, when useful, in one compact chapter provenance note.

The repository should evolve by accumulating verified knowledge, not by rewriting theory.

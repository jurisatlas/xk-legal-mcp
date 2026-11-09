---
name: xk-legal-mcp-skill
description: Official Kosovo (XK) legislation, multi-tier court precedent research, and citation verification skill.
version: 2.0.0
author: JurisAtlas
license: MIT
---

# Kosovo Legal Research & Multi-Tier Case Law Skill (`xk-legal-mcp`)

Use this skill whenever the user asks a legal question, drafts a pleading or contract, or researches case law across any judicial instance in **Kosovo (XK)**.

## Verification & Research Rules

1. **Citation Verification:** Never fabricate a statutory provision or case citation. Query `search_legislation`, `search_case_law`, `search_tiered_court_decisions`, or `verify_citation` before citing any authority (e.g., `AGJ 123/2024 or Ligji Nr. 08/L-123`).
2. **Multi-Tier Judicial Coverage:**
   - **First Instance (Trial / Municipal / District):** 7 Gjykatat Themelore (Basic Courts: Prishtinë, Prizren, Pejë, Gjilan, Gjakovë, Mitrovicë, Ferizaj) & Gjykata Komerciale (First Instance Chambers)
   - **Second Instance (Cantonal / Regional / Appellate):** Gjykata e Apelit e Kosovës (Court of Appeals in Prishtinë) & Gjykata Komerciale (Second Instance Chambers)
   - **Supreme & Constitutional Instance:** Gjykata Supreme e Kosovës (supreme.gjyqesori-rks.org) & Gjykata Kushtetuese (gjk-ks.org)
   - **Primary Tiered Database:** Këshilli Gjyqësor i Kosovës - Regjistri i Vendimeve Gjyqësore (gjyqesori-rks.org) (`https://www.gjyqesori-rks.org/aktgjykimet/`)

# BRANDING.md - FINAL
## Product name: **StudySetu** | Tagline: **A Personalized Learning Platform for Every Student.**
Frozen on 2026-07-15 by team decision. The analysis below is retained as the decision record. Per the naming rule, infrastructure names remain generic; StudySetu appears in config branding, UI, docs, and the domain.

---

# BRANDING.md - Product Naming Decision Document
Purpose: name candidates, evaluation, conflict findings, and the freeze procedure. The name lives ONLY in config/app.yaml (branding block), UI copy, docs, and the domain. Infrastructure is name-agnostic by design (README_BIBLE.md NAMING rule), so this decision can be made late and changed cheaply.

## Conflict findings that reshape the decision (verified July 2026)
- **SETU (current working title):** an existing "SETU" education app by an IIT Kharagpur initiative is on the Play Store, and "Setu" carries heavy government associations (Aarogya Setu). As a bare name it is NOT cleanly ownable.
- **Saarthi (obvious alternative):** crowded to the point of unusable: Saarthi Pedagogy is an Ahmedabad-based K-12 EdTech company (your own city), plus multiple "Saarthi Education" apps on Play Store and App Store. Avoid entirely.
- General caution: single-word Sanskrit/Hindi virtue-nouns (Disha, Gyan, Vidya, Shiksha, Bodhi) are saturated across Indian EdTech. Compound or less-common words differentiate better.
- Before FREEZING any name: 10-minute check: Play Store search, plain Google search, ipindia.gov.in trademark public search (Class 41 Education + Class 9 Software), and domain availability. A hackathon does not require a trademark; it requires not demoing a name the judges recognize as someone else's product.

## The candidates

| # | Name | Meaning and fit | Strengths | Drawbacks | Verdict |
|---|---|---|---|---|---|
| 1 | **Anvaya** (अन्वय: connection, logical sequence) | Literally names the product's thesis: concepts connected in logical order: the concept graph as a brand | Distinctive, premium sound, near-zero EdTech collisions found, 2-second judge explanation ("Sanskrit for connection: because we connect every doubt to its root concept"), works in French pronunciation | Meaning unknown to most: needs the one-liner; slight risk of misspelling (Anvya/Anvaya) | **TOP RECOMMENDATION** |
| 2 | **Sopaan** (सोपान: staircase, steps) | Microlearning steps + mastery ladder; every lesson a step | Concrete visual metaphor (logo draws itself), warm, uncommon in EdTech | Double-a spelling wobble (Sopan/Sopaan); staircase metaphor slightly undersells the doubt engine | Strong runner-up |
| 3 | **StudySetu** (your direction) | Bridge between levels, doubts and understanding | Keeps the Setu meaning you like; compound form differentiates from bare SETU; instantly parseable to Indian judges | Aarogya Setu shadow; IIT-KGP SETU app adjacency; "Study-" prefix reads slightly generic/utility-grade rather than premium | Acceptable; least risky of the Setu family if you want continuity |
| 4 | **Nivaran** (निवारण: resolution, remedy) | "Doubt nivaran" is the literal Hindi phrase for doubt resolution: the product IS shanka-nivaran | Native-phrase resonance is unbeatable for Indian judges; confident sound | Leans on the doubt half only; some coaching institutes use the word informally | Strong if doubt-resolution is your demo centerpiece |
| 5 | **Samajh** (समझ: understanding) | The outcome, not the mechanism: "ab samajh aaya" is the emotional payoff moment | Warm, emotional, memorable, colloquial | Hard for the French jury to pronounce (the 'jh'); common noun = weak ownability | Keep as tagline material ("Ab aayegi samajh"), not the name |
| 6 | **Ekagra** (एकाग्र: one-pointed focus) | Focused, personalized attention per student | Premium sound, rare | Fit is generic (any study app could claim focus); doesn't name our differentiator | Rejected |
| 7 | **Bodhika** (बोधिका: that which awakens understanding) | Awakening comprehension, feminine-suffixed Bodhi | Elegant, uncommon | Bodhi-family names are semi-saturated in tech (Bodhi Linux etc.); slightly ornate | Rejected |
| 8 | **LearnLoop** | The core loop: diagnose -> learn -> doubt -> re-diagnose | English clarity, describes the adaptive cycle, easy globally | Generic Anglo-SaaS energy; multiple small products share it; zero Indian identity for an Indo-French Indian-classroom product | Rejected |
| 9 | **Sutra / SutraLearn** (सूत्र: thread) | Threads connecting concepts = graph edges | Beautiful graph metaphor | "SUTRA" is an existing LLM brand (Two AI) and the word is widely used in tech | Rejected: active AI-space collision |
| 10 | **Disha** (दिशा: direction) | Guides each student in the right direction | Universally understood | One of the most-used names in Indian education (institutes, govt schemes, apps) | Rejected: saturated |
| 11 | **Margam / Maargika** (मार्ग: path) | Personalized path through the curriculum | Path = learning-path fit | Marg-family names common in coaching; Margam also a Bharatanatyam term with its own identity | Rejected |
| 12 | **Parakh** (परख: discernment/assessment) | Diagnostic-first product | Sharp, short | HARD conflict: PARAKH is literally NCERT's national assessment centre: demoing this name to education judges is a self-own | Rejected: do not use |

## Recommendation
1. **Anvaya**: unique, premium, and it names the architecture itself; the judge line writes itself: "Anvaya means connection: we connect every doubt to the concept where it truly began." Pair with tagline "Every doubt has a root." Check `anvaya.app` / `anvaya.me` style domains at freeze time.
2. If the team prefers familiarity over distinctiveness: **StudySetu**, accepting the Setu-family adjacency, with tagline "Bridging every learning gap."
3. Freeze procedure: run the 10-minute conflict check on the chosen name -> claim the domain (INFRA_SETUP_GUIDE Section 9) -> set config/app.yaml branding block -> one MEMORY.md entry -> done. Nothing else in the system changes: that is what the naming rule bought us.

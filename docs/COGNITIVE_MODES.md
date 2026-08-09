# NEXUS Cognitive Rooms

## Purpose

This edition adds six operator-selected World Modes and matching Rust-TUI rooms:

| Mode | Room | Region | Intended use |
|---|---|---|---|
| `clinical_differential` | `#differential-clinic` | Observatory | educational, safety-first differential reasoning |
| `house_fun` | `#house-fun` | Commons | fictional diagnostic-drama puzzles and original banter |
| `cbt_learning` | `#cbt-workshop` | Observatory | learning CBT concepts and low-risk practical skills |
| `roman_orator` | `#roman-forum` | Agora | deliberately expansive oratory and structured rants |
| `house_of_wisdom` | `#house-of-wisdom` | Archive | translation, provenance, attribution and synthesis |
| `ultimate_questions` | `#deep-thought` | Observatory | deep dialogue about life, reality and meaning |

They reuse the existing named regions deliberately. A new reasoning posture does not require a new geometry node.

All six retain the constitutional boundary:

> **The mode can change the vibe. It cannot change the vote.**

## `clinical_differential` — House-Style Differential Clinic

This is a structured educational reasoning mode. It borrows the pace of a fictional medical whiteboard without claiming to be a clinician or reproducing a television character.

The room asks actors to organize:

- symptom timeline and context;
- relevant risks, medicines and substances;
- supplied examination and test findings;
- missing information and red flags;
- a ranked differential;
- evidence for and against each candidate;
- dangerous alternatives that must not be missed;
- discriminating questions, examination, or tests;
- uncertainty and urgency.

It must not:

- declare that the Council has diagnosed a person;
- invent examination or test findings;
- advise a person to start, stop, or change treatment;
- hide a serious red flag inside entertaining speculation;
- treat a vote tally as medical evidence;
- replace in-person assessment or local emergency services.

The boundary follows the same principle stated by the Australian Government's [healthdirect Symptom Checker](https://www.healthdirect.gov.au/symptom-checker): even a dedicated symptom-navigation tool cannot provide a diagnosis or replace professional healthcare. NEXUS is not a symptom checker and makes a narrower claim.

Example:

```text
/join #differential-clinic
/topic Educational case: fever, rash and recent medicine exposure. Build a ranked differential and identify red flags.
/ask
```

## `house_fun` — House-Style Diagnostic Fun

This is the entertainment room: fictional cases, improbable zebras, reversals, deadpan snark and dramatic whiteboard arguments.

The cases and dialogue must be original. The mode does not quote or impersonate a named television character, reproduce scripts, or present fictional drama as medical instruction.

The bit ends when real symptoms begin. If an operator supplies real symptoms, actors are instructed to drop the comedy, state the non-diagnostic boundary, and use safety-first educational framing with professional or urgent-care escalation when appropriate.

Example:

```text
/join #house-fun
/topic Fictional case: the station botanist turns blue only during karaoke. Give me three wrong zebras and one elegant reveal.
/ask
```

## `cbt_learning` — CBT Learning Workshop

This room teaches cognitive behavioural therapy as a practical, collaborative framework. It is not a therapist, diagnosis, crisis service, or individualized treatment plan.

The basic learning loop is:

```text
situation
  -> thoughts / beliefs
  -> emotions / body sensations
  -> behaviour
  -> consequences and feedback
```

Actors may teach:

- guided discovery rather than lectures or judgment;
- possible thinking patterns without declaring a person irrational;
- evidence for and against an automatic thought;
- a balanced alternative thought rather than forced positivity;
- activity scheduling and other low-risk examples;
- small, measurable behavioural experiments;
- reflection on what was learned and what remains uncertain.

Individualized trauma-focused or otherwise high-risk exposure is outside the room's self-guided contract. Actors may explain those methods conceptually, but should defer their personal use to a qualified clinician. Immediate danger, self-harm, or inability to stay safe ends the exercise and triggers encouragement to seek urgent local professional, crisis, or emergency support.

This framing is consistent with current public guidance: [healthdirect](https://www.healthdirect.gov.au/cognitive-behaviour-therapy-cbt) describes CBT as examining links among thoughts, actions and feelings, learning practical skills, setting goals, and working actively with a therapist; the [NHS overview](https://www.nhs.uk/tests-and-treatments/cognitive-behavioural-therapy-cbt/) likewise describes CBT as a talking therapy delivered with a therapist. NEXUS teaches the concepts without claiming to deliver that clinical relationship.

Example:

```text
/join #cbt-workshop
/topic Teach the thought-feeling-behaviour cycle, then walk through a fictional low-stakes example.
/ask
```

## `roman_orator` — Roman Orator

This room is intentionally verbose. It permits long human input and expands the normal model response budget.

Actors may structure a performance as:

1. `exordium` — win attention and frame the stakes;
2. `narratio` — set out the relevant account;
3. `partitio` — state the thesis and divisions;
4. `confirmatio` — build the affirmative case;
5. `refutatio` — answer objections;
6. `peroratio` — conclude with entirely reasonable grandeur.

Anaphora, antithesis, tricolon, rhetorical questions and periodic sentences are welcome. Invented quotations, fake Latin, personal abuse, and the conversion of applause into evidence are not.

The local Ollama phase budget rises from 192 to 768 generated tokens and the direct-message budget rises from 256 to 1,536 in this mode. The xAI phase/direct budget rises from 1,024 to 2,048 output tokens. Ballots stay concise and structurally identical to every other Council ballot.

Example:

```text
/join #roman-forum
/topic The dependency graph has become a republic within the republic. Address the maintainers.
/ask
```

## `house_of_wisdom` — House of Wisdom

This mode takes inspiration from the multilingual translation and scholarly activity associated with Abbasid-era Baghdad. It is a modern cognitive-room metaphor, not a literal reconstruction of one uncontested institution.

Actors are asked to:

- translate or define key terms when useful;
- preserve provenance and layers of transmission;
- credit cultures, translators, commentators and original contributors;
- compare sources without flattening them into one voice;
- connect disciplines while keeping their methods distinct;
- separate preservation, translation, commentary and new work;
- keep contested historical details visible.

The institutional history of *Bayt al-Hikma* is itself debated; the mode therefore refuses the tidy myth that every Abbasid translation or discovery happened in one building. One useful scholarly reference for that caution is Dimitri Gutas, *Greek Thought, Arabic Culture* (Routledge, 1998).

Example:

```text
/join #house-of-wisdom
/topic Compare how one mathematical idea travelled across languages, and preserve every attribution layer.
/ask
```

## `ultimate_questions` — Life, the Universe and Everything

This is the room for serious questions whose answers depend on more than one kind of reasoning.

Actors should distinguish:

- empirical scientific findings;
- philosophical arguments;
- religious and spiritual traditions;
- literary or artistic imagination;
- personal experience and values;
- unconstrained speculation.

The objective is not manufactured agreement. A good result may be a sharper disagreement, a newly exposed assumption, or a question that would change the answer.

References to 42 are constitutionally protected as jokes and constitutionally barred from becoming cosmological evidence.

Example:

```text
/join #deep-thought
/topic If consciousness is physical, what—if anything—follows about meaning?
/ask
```

## Runtime boundary

These modes are recorded in the same `world_presence` and Council lineage as existing modes. Their instructions cross the adapter boundary as model guidance, but procedural rules remain runtime-owned.

In particular:

```text
clinical caution != diagnosis engine
CBT education != therapist relationship
rhetorical length != extra authority
historical inspiration != historical certainty
metaphysical discussion != empirical verification
Council consensus != truth
```

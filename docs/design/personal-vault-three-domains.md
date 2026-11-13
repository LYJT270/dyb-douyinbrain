# Personal vault: life, work and learning

Implemented for 1.7.0. Pre-release behavior evidence is recorded in [the candidate verification](../verification/three-domains-candidate.md); publication evidence belongs to the 1.7.0 Release verification appendix.

## User-visible contract

The vault supports everyday life, work and learning. New onboarding asks which of these the user most wants help with. That selection starts the interview; all three domains participate after vault opt-in. Creative/media tasks remain supported under work, and existing creative records remain readable.

An interview continues until the user pauses, stops or changes topic. Fixed profile fields being populated never completes the interview. Ask one useful question at a time, reuse existing records, preserve skipped topics, and resume the current thread in another chat. A concrete task takes priority. Ordinary tasks use relevant context without automatically becoming interviews.

Life covers background and significant experiences, values and decision-making, routines and energy, relationships and responsibilities, finances and constraints, and goals. Work covers career, projects, business and creative output. Learning covers understanding, practice, application and feedback. These are guides for relevant questions, not mandatory questionnaires.

## Storage and compatibility

New content lives under `生活/`, `工作/` and `学习/`. Subdirectories grow on demand. Common profile and cooperation preferences belong to `生活/个人档案/`; project/account-specific facts stay scoped to their projects. Preserve source answers and references separately from derived knowledge. Record current state, historical events and future intentions distinctly. User statements, subjective experience and unconfirmed model interpretations remain distinguishable.

Existing users also reclassify their full content library. An Agent reads existing navigation, proposes file mappings based on actual contents and asks about unresolved classifications. The runtime validates a concrete preview, backs up originals before applying, repairs supported links/navigation/runtime targets, verifies results, and supports recovery. It never guesses classifications, overwrites conflicting files, rewrites source prose, deletes original evidence or silently migrates a real library during installation. Existing library rules and publication entry points must be represented in the preview and respected.

Historical receipts remain evidence of past writes. Moving files must preserve the relationship between old targets and current locations rather than silently rewriting historical facts. Pending writes must be resolved or explicitly diagnosed before moving their targets.

Migration holds the same library-level exclusive lock as local publication, rechecking file hashes, rules and inventory inside that boundary. External writers must support the migration through their actual entry point; otherwise planning returns an actionable awaiting-writer diagnosis. A migration journal records each step and before/after hashes. Recovery only restores files whose current content matches a recorded migration state, preserving later human edits as conflicts. A separate source/target and hash projection resolves historical receipt references without modifying those receipts.

## Participation and progress

An opted-in agent-scoped entry participates in relevant everyday chats without requiring the user to name the skill. Workspace-only scope remains available. Descriptions improve implicit discovery; a short host instruction pointer leads to the shared workflow. Context loading stays relevant to the task. Host instructions are not a background event service, and real new-chat behavior must be verified separately from static installation.

Explicit new personal facts, changed goals and actual outcomes can be accumulated within the opted-in scope; ordinary conversation is not indiscriminately archived. Respect no-save, paused collection and paused interviews. Preserve original statements and verify important interpretations. Mention material updates or assumptions briefly. Occasionally invite the user to start another unstarted domain, after checking existing/imported information; paused/refused topics are not nagged.

## Updates

When the official GitHub stable Release is newer than the installed version, remind once in every chat in which the suite participates. A reminder in one chat must not suppress another chat. Repeated commands in one chat do not repeat the same notice. Release metadata can remain cached for 24 hours independently of reminder deduplication. Support an explicit session ID and a genuine host session ID when available; without one return a notice for the Agent to deduplicate in conversation rather than inventing a global chat identity. A command returning a notice is not proof the user saw it. Update only on an explicit update request. After installation catches up, old notices stop. Network failure does not interrupt the user's task; previously confirmed release information must remain identifiable as cached/stale.

Store per-session notice claims independently of the shared release metadata so concurrent chats cannot erase one another's deduplication. Explicit session identities are hashed locally; the cache contains no chat transcript.

## Implementation boundaries and checks

Reuse the existing context, answer, staging, locking, expected-hash and publication contracts. Extend existing commands rather than creating a new service or database. Preserve old module/field inputs as compatibility aliases. Changes are source-only until isolated checks pass; live library migration requires its own concrete preview. Publishing and production installation are separate authorized stages.

Tests use temporary libraries and mocked release metadata. Cover domain onboarding and free topic answers, cross-domain context and original provenance, interview/collection pauses, legacy compatibility, complete reclassification with links and runtime entries, collisions/concurrent edits/recovery, and per-chat update notices with shared cache/offline/install-caught-up cases. Existing media/text behavior must remain valid. Final source checks, isolated installation and package verification must use the candidate files; fresh-chat claims require actual observed chat behavior.

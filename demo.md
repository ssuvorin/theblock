# DEMO FLOW — FIND ME A CRYPTO PRODUCT ROLE IN DUBAI

## Core demo claim

The demo starts with a real job-search problem:

> Which relevant companies are hiring now?

Then it adds the product’s differentiator:

> Who do I already know who can help me reach those opportunities?

Context.dev searches the public market. Convex and the canonical relationship graph reconstruct private network evidence. The final answer connects each verified opportunity or hiring signal to known people and warm paths, with separate public and private citations.

---

## User query

> I’m looking for a Product Manager role at a crypto company in Dubai.
>
> Which relevant companies are hiring now?
>
> Who do I already know who could help me, and which warm paths should I follow first?

---

# STEP 1 — UNDERSTAND THE JOB GOAL

The system extracts:

```text
ROLE
Product Manager

RELATED ROLES
Senior Product Manager
Product Lead
Product Owner
Head of Product

INDUSTRY
Crypto / Web3 / Digital Assets

LOCATION
Dubai / UAE

ACTION
Find current opportunities, then identify warm paths through my network
```

On screen:

```text
UNDERSTANDING YOUR GOAL

Product Manager
Crypto / Web3
Dubai / UAE
Current opportunities + warm paths
```

The user can correct the extracted role, industry, location, or related titles before search.

---

# STEP 2 — SEARCH THE JOB MARKET FIRST

This is the first major reveal.

The product calls Context.dev `POST /web/search` with bounded, goal-specific queries. P0 requests 10–30 results, localizes to the UAE, applies a freshness window, and prioritizes first-party career pages and public applicant-tracking systems.

Example query intent:

```text
("Product Manager" OR "Senior Product Manager" OR "Product Lead")
(crypto OR web3 OR "digital assets")
(Dubai OR UAE)
(jobs OR careers OR hiring)
```

Search targets can include:

- company career pages;
- Greenhouse, Lever, Ashby, and other public ATS pages;
- public role announcements;
- company expansion or UAE-office announcements.

The product does not log in to or scrape LinkedIn.

On-screen transition:

```text
SEARCHING CURRENT OPPORTUNITIES

Context.dev Web Search
UAE localized
Fresh public evidence
10–30 bounded results
```

Raw results stream into the application as source cards with URL, title, source domain, excerpt, publication date when available, and checked time.

---

# STEP 3 — VERIFY AND NORMALIZE OPPORTUNITIES

The system separates confirmed vacancies from weaker market signals.

## Verified open role

A result receives `VERIFIED OPEN ROLE` only when a currently accessible public source explicitly provides:

- role title;
- company;
- Dubai/UAE location or applicable remote eligibility;
- an open vacancy or application state;
- a public source URL checked during the search.

## Hiring signal

A result receives `HIRING SIGNAL` when it shows:

- team expansion;
- a new UAE office;
- recent funding;
- a relevant product launch;
- a careers page without a matching confirmed role.

## Unverified

An ambiguous, stale, inaccessible, or snippet-only result is labeled `UNVERIFIED`. It is never presented as a current vacancy.

Context.dev `/brand/retrieve` enriches resolved organizations with logo, description, industry, domain, and socials. Brand data describes the company but does not prove hiring.

On screen:

```text
6 RELEVANT RESULTS

3 VERIFIED OPEN ROLES
2 HIRING SIGNALS
1 UNVERIFIED
```

Every card keeps its public citation and last-checked timestamp.

---

# STEP 4 — SEARCH MY NETWORK FOR EACH OPPORTUNITY

Now the product moves from public market data into the user’s private relationship memory.

For the job goal and each resolved company, the system searches Convex for interaction evidence related to:

- the company and its domain;
- product leadership;
- crypto, Web3, payments, and digital assets;
- Dubai, UAE, relocation, or regional expansion;
- introductions, founders, investors, recruiters, and hiring discussions;
- prior offers to help;
- recent and historically strong relationships.

Technical flow shown briefly:

```text
Context.dev opportunities
  → resolve organizations
  → embed goal/company context
  → Convex semantic search
  → aggregate chunks by person
  → PostgreSQL relationship graph
  → rank warm paths
```

The query uses `openai/text-embedding-3-small` through OpenRouter. Convex results remain scoped to the current owner and return source/time/person/citation metadata.

Hundreds of relationship points appear. Non-relevant contacts fade until only people connected to the discovered opportunities or the broader goal remain.

On-screen text:

```text
NOW SEARCHING YOUR NETWORK

Not just who matches the topic.
Who can create a credible path to this opportunity?
```

---

# STEP 5 — RECONSTRUCT THE WARM PATHS

## Opportunity 1 path

```text
YOU
  ↓ know
MARTA
  ↓ VP Product at
COMPANY X
  ↓ public careers evidence
PRODUCT MANAGER — DUBAI
```

Private relationship evidence:

```text
Met at TOKEN2049
Introduced by Alex
Discussed digital-asset infrastructure
Last interaction: 8 months ago
```

Public opportunity evidence:

```text
Company careers page
Product Manager
Dubai
Checked today
```

## Opportunity 2 path

```text
YOU
  ↓ know
JOHN
  ↓ cited portfolio relationship
COMPANY Y
  ↓ public ATS evidence
SENIOR PRODUCT MANAGER — UAE
```

Private relationship evidence:

```text
Strong direct relationship
Previously discussed portfolio introductions
```

## Opportunity 3 path

```text
YOU
  ↓ recently met
SERGEY
  ↓ founder of
COMPANY Z
  ↓ public expansion evidence
HIRING SIGNAL — UAE PRODUCT TEAM
```

This path is explicitly weaker because no matching open role was verified.

Path rules:

- private relationship edges require imported evidence or an explicit owner-created link;
- opportunity claims require current public Context.dev evidence;
- shared employment alone does not prove that an introduction is possible;
- public market evidence never exposes private messages;
- private citations and public URL citations are displayed separately.

Visually, this is the key moment: current opportunities appear first, then three warm paths illuminate across the relationship graph.

---

# STEP 6 — SHOW THE REAL APP ANSWER

Transition to the real application.

Prompt shown:

> I’m looking for a Product Manager role at a crypto company in Dubai. Which relevant companies are hiring now? Who in my network could help me, and which warm paths should I follow first?

Example answer:

> I found three verified or high-confidence public opportunities and two additional hiring signals relevant to crypto product work in Dubai/UAE.
>
> You have evidence-backed warm paths into two of the companies. Marta is the strongest direct path, John may provide an introduction to a second company, and Sergey is relevant to an expansion signal that does not yet include a verified open role.

Results are opportunity-first.

## Opportunity 1 — Company X

```text
STATUS
Verified open role

ROLE
Product Manager

LOCATION
Dubai

GOAL FIT
Strong

PUBLIC EVIDENCE
First-party careers page
Checked today

YOUR WARM PATH
You → Marta → Company X

RELATIONSHIP CONTEXT
Met at TOKEN2049
Introduced by Alex
Discussed digital-asset infrastructure
Last interaction: 8 months ago

RECOMMENDED ACTION
Reconnect with Marta and ask for perspective on the role and team
```

Citations:

- `PUBLIC SOURCE` opens the current vacancy page;
- `RELATIONSHIP SOURCE` opens the exact imported interaction or accepted relationship evidence.

Primary CTA:

```text
DRAFT MESSAGE TO MARTA
```

## Opportunity 2 — Company Y

```text
STATUS
Verified open role

ROLE
Senior Product Manager

LOCATION
UAE

GOAL FIT
Strong

YOUR WARM PATH
You → John → Company Y

RECOMMENDED ACTION
Ask John whether he can introduce you to the relevant product leader
```

Primary CTA:

```text
DRAFT INTRO REQUEST
```

## Opportunity 3 — Company Z

```text
STATUS
Hiring signal — no matching open role verified

SIGNAL
Expanding UAE product team

YOUR WARM PATH
You → Sergey → Company Z

RECOMMENDED ACTION
Reconnect before a role is publicly advertised
```

The UI must not call this a confirmed vacancy.

Primary CTA:

```text
RECONNECT
```

## Opportunity without a warm path

A verified role may have no known relationship path. Show it honestly:

```text
VERIFIED OPPORTUNITY
No warm path found in your current network
```

This proves the system does not fabricate connections.

---

# STEP 7 — ACT WITHOUT AUTO-SENDING

The user selects `Draft message` for Marta.

The assistant creates an editable draft grounded in the selected opportunity and cited relationship context:

> Hi Marta,
>
> It has been a while since TOKEN2049. I enjoyed our conversation about digital-asset infrastructure. I noticed the Product Manager role at Company X in Dubai and I’m currently exploring product opportunities in the crypto space. Would you be open to a quick catch-up and sharing your perspective on the team?

Available actions:

```text
Edit
Copy
Open external client
Remind me
Save opportunity
Save follow-up
```

P0 does not send or apply automatically. `Copy` copies the final text, `Open external client` hands off to a user-controlled application, `Remind me` creates a follow-up, and `Save opportunity` stores the cited public result for later review.

---

# FINAL INSIGHT

Return to the combined opportunity and relationship graph.

```text
A JOB SEARCH ENGINE CAN TELL YOU WHO IS HIRING.
A CRM CAN TELL YOU WHO YOU KNOW.

SECOND BRAIN CONNECTS THE OPPORTUNITY
TO THE PERSON WHO CAN HELP YOU REACH IT.
```

Final screen:

```text
FIND THE OPPORTUNITY.
FIND THE PERSON.
FOLLOW THE WARM PATH.

YOUR NETWORK SHOULD REMEMBER ITSELF.
```

---

# Demo verification checklist

- The goal parser extracts role, related roles, industry, location, and desired action.
- Context.dev `/web/search` runs before private-network retrieval.
- Search is bounded, UAE-localized, fresh, and credit-budgeted.
- Every current-vacancy claim has an accessible public citation and checked timestamp.
- Hiring signals and unverified results are visually distinct from verified open roles.
- Context.dev `/brand/retrieve` enriches organizations but is not used as vacancy proof.
- Convex retrieves owner-scoped semantic relationship evidence for the goal and resolved companies.
- Retrieved chunks are aggregated by person before graph expansion.
- PostgreSQL reconstructs evidence-backed people and warm paths.
- At least one Collabute meeting/action item contributes to a warm-path recommendation.
- At least one Evolution message contributes to a warm-path recommendation.
- Public opportunity citations and private relationship citations remain separate.
- At least one verified opportunity with no warm path is shown when the corpus supports it.
- Draft generation uses the selected opportunity and cited relationship context.
- Draft actions are edit/copy/external handoff/reminder/save; no automatic sending or application occurs.
- No-evidence states produce honest empty/partial results instead of fabricated vacancies or contacts.

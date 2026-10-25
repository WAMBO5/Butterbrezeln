# Risk classification under the EU AI Act

**Legal review: pending.** This is the engineering team's reading, written for legal counsel to confirm or correct before the system is placed on the market or used for compliance work.

## The system

Certivity's requirements engine reads a vehicle component's specification and/or exploded view and drafts the engineering requirements the component must meet under the UN Regulations of a fixed corpus, each cited to regulation, version, page and paragraph. It also shows how those requirements split across illustrative markets. Engineers review and sign off the output; the system takes no decision about a vehicle or a person.

## Our role

We are the **provider** of an AI system that integrates a general-purpose AI model (Anthropic). The obligations for general-purpose models (Articles 53–55) rest with the model provider. The technical file records the model ids used in each run.

## Reading

| Question | Reading |
| --- | --- |
| Prohibited practice (Art. 5)? | No. |
| Safety component of a product under Annex I legislation (Art. 6(1))? | No. The system is not part of a vehicle and does not perform a safety function. Its output informs engineers who prepare type approval. |
| Annex III use case (Art. 6(2))? | Not on our reading: it does not decide on access to services, employment, education, law enforcement, migration or justice, and it is not critical-infrastructure management. |
| Transparency obligations (Art. 50)? | Yes: its output is AI-generated text and is labelled and marked as such. |
| AI literacy (Art. 4)? | Yes: users get instructions for use and an in-app guide. |

**Provisional classification:** not high-risk; Article 50 and Article 4 apply.

**Design decision:** because the output feeds type approval of safety-relevant products, the system is built to the high-risk requirements of Articles 9–15 anyway (risk management, data governance, technical documentation, record-keeping, transparency, human oversight, accuracy and robustness). A stricter classification would change paperwork, not architecture.

## Application dates

The application dates of the high-risk obligations have been subject to proposed amendments. Legal counsel fills in the dates in force at release:

| Obligation | Applies from |
| --- | --- |
| Prohibitions and AI literacy (Art. 5, Art. 4) | to be confirmed by legal |
| General-purpose AI model obligations | to be confirmed by legal |
| Transparency (Art. 50) | to be confirmed by legal |
| High-risk obligations (Art. 6–49) | to be confirmed by legal |

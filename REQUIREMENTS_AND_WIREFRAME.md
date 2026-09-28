# Requirements and wireframe

## Requirements

- Map all 18 claims to two photos each using claim_photo_mapping.csv.
- Display the selected claimant and both assigned photos.
- Run Google Vision Web Detection for all 36 photos and record full matches, partial matches, matching pages, and best-guess labels.
- Compare 256-bit perceptual hashes across claims (distance <= 10) and detect shared full-matching web images.
- Apply R0-R4: escalate for incomplete lookups/comparisons, cross-claim reuse, amounts >= $7,500, or a prior claim by the same person within 30 days.
- Record public web matches without escalating in class mode; the production setting escalates full public web matches.
- Record narrative and later-claim links as notes; they do not independently change the decision.
- Show all 18 decisions and a reused-photo evidence table after analysis.
- Show full lookup evidence in the app and prefill a concise summary into Google Forms.
- Require Claim ID, Claimant Name, Lookup Findings and Decision in the form.
- Collect a verified Google email and leave final submission to the reviewer.
- Store the API key in .env or Streamlit Secrets, outside the website.

## Wireframe

```text
ClaimGuard
Select a claim [Claim ID, claimant, amount v]
Claimant name
[Photo 1] [Photo 2]
[Analyze photos]

Decision: auto-approve or escalate
[Full lookup findings]
[Open prefilled review form]
[All claim decisions]
[Reused-photo evidence]

Google Form
[ ] Confirm signed-in email
Claim ID        [prefilled]
Claimant Name   [prefilled]
Lookup Findings [prefilled summary]
Decision        [prefilled]
[Submit]
```

Changing claims displays the selected claim's results from the last analysis. Running analysis again refreshes all 36 lookups. Prefilled answers remain editable for human review. Google Forms stores responses; the app does not submit them. The short summary prevents oversized prefill URLs, while full web evidence remains available in the app. Form draft autosave is disabled so older claim answers do not replace the current prefill. The published form link and run instructions are in README.md.

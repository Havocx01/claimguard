# ClaimGuard

ClaimGuard checks insurance claim photos for reuse and recommends whether to auto-approve the claim or send it for human review.

## Setup

```powershell
py -m pip install -r requirements.txt
py -m streamlit run app.py
```

## How it works

1. Select a claim. The app displays the claimant and two photos listed in `claim_photo_mapping.csv`.
2. Click **Analyze photos**. The app checks all 36 photos with Google Vision Web Detection and compares 256-bit perceptual hashes across claims. Switching claims reuses the results; clicking Analyze photos again refreshes all lookups.
3. Review the decision and findings. Cross-claim reuse, incomplete checks, amounts of $7,500 or more, or a previous claim by the same claimant within 30 days trigger escalation. Public web matches are recorded but do not trigger escalation for the class dataset. Narrative similarity is recorded only as a note.
4. Click **Open prefilled review form**. The form contains the claim ID, claimant name, lookup summary, and decision. Full web evidence remains visible in the app.
5. Confirm your signed-in Google email and click **Submit** yourself. The app does not fill the email or submit the form.

Responses are saved in Google Forms. Finish the review before closing or refreshing the form because draft autosave is disabled.

## Configuration

Set `GOOGLE_VISION_API_KEY`, `GOOGLE_FORM_URL`, `FORM_CLAIM_ID`, `FORM_CLAIMANT`, `FORM_FINDINGS`, and `FORM_DECISION` in `.env` locally or in Streamlit Secrets when deployed. Never commit the key.

The thresholds are at the top of `app.py`: `amountLimit`, `repeatDays`, `hashLimit`, and `ESCALATE_ON_PUBLIC_WEB_MATCH`. The web-match setting is off for the class dataset; enabling it escalates full public web matches. Cross-claim reuse means a perceptual-hash distance of 10 or fewer bits, or a shared full-matching web image.

The expandable tables show all claim decisions and reused-photo evidence. Any incomplete comparison prevents approval. The expected 7 escalations and 11 approvals assume successful lookups without additional shared web matches.

## Review form

[Open the ClaimGuard review form](https://docs.google.com/forms/d/e/1FAIpQLSe2pKUj-e5rVueFBaKexUjzRjsIQZyM2u24Df-UDzkUxK91EQ/viewform)


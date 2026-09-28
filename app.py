import base64
import csv
import logging
import os
from datetime import date
from pathlib import Path
from urllib.parse import urlencode

import imagehash
import requests
import streamlit as st
from dotenv import load_dotenv
from PIL import Image

amountLimit = 7500
repeatDays = 30
hashLimit = 10
ESCALATE_ON_PUBLIC_WEB_MATCH = False

folder = Path(__file__).resolve().parent
load_dotenv(folder / '.env')
apiKey = os.getenv('GOOGLE_VISION_API_KEY', '').strip()
formUrl = os.getenv('GOOGLE_FORM_URL', '').strip()

claims = {}
with open(folder / 'claim_photo_mapping.csv', newline='', encoding='utf-8') as file:
    for row in csv.DictReader(file):
        row['Amount'] = int(row['Amount'])
        row['Date'] = date.fromisoformat(row['Date'])
        claims[row['Claim ID']] = row


def checkPhoto(photoName):
    result = {'hash': None, 'fullMatches': set(), 'findings': [], 'complete': False}
    try:
        photoPath = folder / 'images' / photoName
        with Image.open(photoPath) as photo:
            result['hash'] = imagehash.phash(photo, hash_size=16)
        photoBytes = photoPath.read_bytes()
        if not apiKey:
            result['findings'].append('R0: ' + photoName + ': Google Vision is not configured.')
            return result

        encodedBytes = base64.b64encode(photoBytes)
        encodedPhoto = encodedBytes.decode('utf-8')
        imageData = {'content': encodedPhoto}
        feature = {'type': 'WEB_DETECTION'}
        photoRequest = {'image': imageData, 'features': [feature]}
        requestData = {'requests': [photoRequest]}
        response = requests.post('https://vision.googleapis.com/v1/images:annotate', headers={'X-Goog-Api-Key': apiKey}, json=requestData, timeout=30)
        response.raise_for_status()
        responseData = response.json()
        data = responseData['responses'][0]
        if 'error' in data:
            result['findings'].append('R0: ' + photoName + ': Google Vision could not check this photo.')
            return result

        web = data.get('webDetection', {})
        matchTypes = {
            'fullMatchingImages': 'full web matches',
            'partialMatchingImages': 'partial web matches',
            'pagesWithMatchingImages': 'matching pages'
        }
        for matchType, label in matchTypes.items():
            matches = web.get(matchType, [])
            result['findings'].append(f'{photoName}: {len(matches)} {label}.')
            for match in matches:
                result['findings'].append(photoName + ' - ' + label + ': ' + match['url'])
                if matchType == 'fullMatchingImages':
                    result['fullMatches'].add(match['url'])
        for guess in web.get('bestGuessLabels', []):
            result['findings'].append(photoName + ': Best-guess label: ' + guess['label'])
        result['complete'] = True
    except (requests.RequestException, OSError, ValueError, KeyError, IndexError, TypeError) as error:
        logging.warning('Photo lookup failed: %s (%s)', photoName, type(error).__name__)
        result['findings'].append('R0: ' + photoName + ': Lookup failed. Check the API configuration or connection.')
    return result


def comparePhotos(photos):
    evidence = []
    claimIds = list(claims)
    for index in range(len(claimIds)):
        claimId = claimIds[index]
        for otherIndex in range(index + 1, len(claimIds)):
            otherId = claimIds[otherIndex]
            for column in ['Photo 1', 'Photo 2']:
                photoName = claims[claimId][column]
                photo = photos[photoName]
                for otherColumn in ['Photo 1', 'Photo 2']:
                    otherName = claims[otherId][otherColumn]
                    other = photos[otherName]
                    methods = []
                    if photo['hash'] is not None and other['hash'] is not None:
                        distance = photo['hash'] - other['hash']
                        if distance <= hashLimit:
                            methods.append(f'perceptual hash: {distance}/256 bits different')
                    shared = []
                    for url in photo['fullMatches']:
                        if url in other['fullMatches']:
                            shared.append(url)
                    if shared:
                        shared.sort()
                        methods.append('shared full web image: ' + ', '.join(shared))
                    if methods:
                        evidence.append({
                            'Claim ID': claimId,
                            'Claimant': claims[claimId]['Claimant'],
                            'Photo': photoName,
                            'Other claim': otherId,
                            'Other claimant': claims[otherId]['Claimant'],
                            'Other photo': otherName,
                            'Method': '; '.join(methods)
                        })
    return evidence


def reviewClaim(claimId, photos, evidence):
    claim = claims[claimId]
    findings = []
    reasons = []
    for column in ['Photo 1', 'Photo 2']:
        photoName = claim[column]
        photo = photos[photoName]
        findings.extend(photo['findings'])
        if not photo['complete']:
            reasons.append('R0: Incomplete lookup for ' + photoName + '.')
        if ESCALATE_ON_PUBLIC_WEB_MATCH and photo['fullMatches']:
            reasons.append('R2: ' + photoName + ' has a full public web match.')

    for match in evidence:
        if match['Claim ID'] == claimId:
            reasons.append(f"R1: {match['Photo']} matches {match['Other photo']} in {match['Other claim']} ({match['Other claimant']}); {match['Method']}.")
        elif match['Other claim'] == claimId:
            reasons.append(f"R1: {match['Other photo']} matches {match['Photo']} in {match['Claim ID']} ({match['Claimant']}); {match['Method']}.")

    for photo in photos.values():
        if photo['hash'] is None or not photo['complete']:
            reasons.append('R0: Cross-claim comparison is incomplete because a photo lookup failed.')
            break
    if claim['Amount'] >= amountLimit:
        reasons.append(f"R3: Amount ${claim['Amount']:,} is at least ${amountLimit:,}.")
    for otherId, other in claims.items():
        if otherId == claimId or other['Claimant'] != claim['Claimant']:
            continue
        days = (claim['Date'] - other['Date']).days
        if days >= 0 and days <= repeatDays:
            reasons.append(f'R4: Same claimant filed {otherId} {days} days earlier.')
        elif days >= -repeatDays and days < 0:
            findings.append('Note: Linked to later claim ' + otherId + '; this does not trigger R4 for the earlier claim.')
    if claim['Note']:
        findings.append('Note: ' + claim['Note'])
    if not ESCALATE_ON_PUBLIC_WEB_MATCH:
        findings.append('R2 is off for the class dataset. Public web matches are recorded only.')
    if reasons:
        decision = 'escalate'
    else:
        decision = 'auto-approve'
        if ESCALATE_ON_PUBLIC_WEB_MATCH:
            reasons.append('R0-R4 passed.')
        else:
            reasons.append('R0-R4 passed under the class settings.')
    return {'decision': decision, 'reasons': reasons, 'findings': findings}


def claimLabel(claimId):
    claim = claims[claimId]
    name = claim['Claimant']
    amount = claim['Amount']
    return f'{claimId} · {name} · ${amount:,}'


st.set_page_config(page_title='ClaimGuard | Meridian Insurance', layout='centered')
st.html("""
<style>
    .stMainBlockContainer { max-width: 960px; padding-top: 3rem; }
    h1 { letter-spacing: -0.03em; }
    [data-testid="stImage"] img { height: 240px; object-fit: contain; border-radius: 12px; }
    [data-testid="stBaseButton-primary"] { background: #16756b; border-color: #16756b; color: white; min-height: 44px; }
    [data-testid="stBaseButton-primary"]:hover { background: #105d55; border-color: #105d55; color: white; }
    [data-testid="stBaseButton-primary"]:focus-visible { outline: 3px solid #58b5a9; outline-offset: 3px; }
    @media (max-width: 640px) {
        .stMainBlockContainer { padding-top: 2rem; }
        [data-testid="stImage"] img { height: auto; max-height: 280px; }
    }
</style>
""")
st.title('ClaimGuard')
st.caption('Meridian Insurance · Claim photo review')
st.divider()
claimId = st.selectbox('Select a claim', list(claims), format_func=claimLabel)
claim = claims[claimId]
st.subheader(claim['Claimant'])
st.caption(f"{claimId} · {claim['Date']} · ${claim['Amount']:,}")

photoColumns = st.columns(2, gap='medium')
for index, column in enumerate(['Photo 1', 'Photo 2']):
    photoName = claim[column]
    photoPath = folder / 'images' / photoName
    with photoColumns[index]:
        if photoPath.is_file():
            st.image(str(photoPath), caption=photoName, width='stretch')
        else:
            st.error('Photo missing: ' + photoName)

st.caption('The first analysis checks all 36 photos. Results are reused until you run the analysis again.')
if st.button('Analyze photos', type='primary', width='stretch'):
    photos = {}
    with st.spinner('Checking all claim photos...'):
        for item in claims.values():
            for column in ['Photo 1', 'Photo 2']:
                photoName = item[column]
                if photoName not in photos:
                    photos[photoName] = checkPhoto(photoName)
        evidence = comparePhotos(photos)
        reviews = {}
        for itemId in claims:
            reviews[itemId] = reviewClaim(itemId, photos, evidence)
        st.session_state['reviews'] = reviews
        st.session_state['evidence'] = evidence

if 'reviews' in st.session_state:
    review = st.session_state['reviews'][claimId]
    st.divider()
    if review['decision'] == 'escalate':
        st.warning('Escalate · Human review required')
    else:
        st.success('Auto-approve · Guardrail checks passed')
    st.subheader('Review and submit')
    allFindings = review['reasons'] + review['findings']
    st.text_area('Lookup findings', value='\n'.join(allFindings), height=220, disabled=True)
    summary = []
    for line in allFindings:
        if ' - ' in line and (': https://' in line or ': http://' in line):
            continue
        if '; shared full web image:' in line:
            parts = line.split('; shared full web image:', 1)
            line = parts[0] + '; shared full web image.'
        summary.append(line)
    summary.append('Full web evidence is shown in the ClaimGuard app.')
    formFields = {
        os.getenv('FORM_CLAIM_ID', ''): claimId,
        os.getenv('FORM_CLAIMANT', ''): claim['Claimant'],
        os.getenv('FORM_FINDINGS', ''): '\n'.join(summary),
        os.getenv('FORM_DECISION', ''): review['decision']
    }
    if not formUrl or '' in formFields or len(formFields) != 4:
        st.error('Set the Google Form URL and field IDs in .env or Streamlit Secrets.')
    else:
        formQuery = urlencode(formFields)
        formLink = formUrl + '?' + formQuery
        st.link_button('Open prefilled review form', formLink, type='primary')
        st.caption('Review the answers in Google Forms, confirm your email, and submit the form yourself.')

    with st.expander('All claim decisions'):
        rows = []
        for itemId, result in st.session_state['reviews'].items():
            rows.append({
                'Claim ID': itemId,
                'Claimant': claims[itemId]['Claimant'],
                'Amount': claims[itemId]['Amount'],
                'Decision': result['decision'],
                'Reasons': '\n'.join(result['reasons'])
            })
        st.dataframe(rows, hide_index=True)
    with st.expander('Reused-photo evidence'):
        if st.session_state['evidence']:
            st.dataframe(st.session_state['evidence'], hide_index=True)
        else:
            st.write('No cross-claim photo matches found in the completed comparisons.')

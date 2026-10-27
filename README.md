# HY Developer Sales Engine

Finds businesses, works out which problems HY Developer can solve for each one, calls them with an AI voice agent,
follows up automatically, and tracks every deal to the close. Runs on your own Windows PC. One owner login.
Nothing to install besides the program itself: the database is a built-in file and API keys are typed into Settings.

## Get the program
See **BUILD_WINDOWS.md**: build `HYSalesEngine.exe` / `Setup.exe` with one double-click, or let GitHub build it for you.

**Quickest:** install Python 3.12, then double-click `start.bat`. It sets itself up and opens the program.

(Developers can also run from source: `cd backend`, `pip install -r requirements.txt`, `python launcher.py`.
The screens are already built in `backend/ui`. To change them, work in `frontend` and run `npm run build`.)

## First start
1. Open the program. Your browser shows **Create your owner account**. Choose an email and a password of at least 10 characters.
   There is no password reset, so keep it safe.
2. **Settings > Integrations > API keys.** Paste each key, press **Save keys**, then **Test this key**:
   - **Language model key:** reads and scores businesses and sorts call results. A free Gemini key from aistudio.google.com works.
   - **Google Places key:** finds businesses automatically. In Google Cloud turn on *Places API (New)* and billing. Set a budget alert first.
   - **Retell key:** from your Retell dashboard.
3. **Settings > Integrations > Your calling phone numbers:** one per line with country code. They stay on this computer.
   Retell's own numbers can only call some countries, so check yours can reach the UAE, Saudi Arabia, the UK, Australia and the USA.
4. **Settings > General:** your time zone and currency. **Settings > Markets:** confirm calling hours for each country.
5. **Settings > Voice Agent:** paste a Retell voice ID for en-US, read the opening line, press **Save and build agent**.
6. **Campaigns and Calling > Test call:** call your own phone first. Listen before any lead is called.
7. **Lead Discovery:** try Find by link on one site, then Auto-find with 10 leads. Or import a CSV or Excel file in **Leads**.
8. Open a lead, read the analysis, then **Call this lead now**, or select several leads and press **Plan calls**.

## How the lead score works
The score follows your Evidence-First scoring document. It is a **priority for outreach, not a chance to buy.**
**Every number below is yours to change** in **Settings > Lead Scoring**. Click a lead's name in **Leads** to see its report: each rating, why, and the page link behind each finding.

**In plain words.** Each lead gets five ratings from 0 to 5. Each rating becomes points: **rating ÷ 5 × weight**. The weight is the most points that factor can give, and the five weights add up to 100.

| Factor | Weight (default) | What earns the rating |
|---|---|---|
| Pain point and impact | 50 | Proven problems count in full, suspected ones count half. One serious proven gap is about a 4, several make a 5. |
| HY service fit | 25 | How directly the strongest gap maps to a service in your Service Catalog. |
| Evidence quality | 15 | 5: an exact page quote, or several measured findings over 8+ pages. 4: measured on the live site. 3: thin data or a Google listing only. 2 or 1: only suspicions. |
| Buying signals | 5 | Public signs of expansion, hiring or a plan to improve, each backed by a quote. None gives 0, not a rejection. |
| Business fit | 5 | Your ideal customer: business types you want, types you avoid, and your target markets. |

**Safety rules** (also editable): no verified pain caps the score at 49. A key pain that is only guessed loses 5 points. A business type on your avoid list is capped at 39.
**Priority bands:** 80 and up High, 60 to 79 Medium, below 60 Low.

**Worked example.** A UAE clinic whose site has no HTTPS (medium problem, measured) and no contact form (low problem, only a missing feature), 10 pages read, no buying signals, your target types not set:
Pain rating 3 gives 30 points. Service fit 4 gives 20. Evidence 4 gives 12. Buying signals 0. Business fit 3 gives 3. Total 65, Medium priority.

**What you can set in Settings > Lead Scoring:** your ideal customer (types you want, types you avoid, target markets), the five weights (they must total 100), the safety rules and band limits,
and the detailed values (points per problem size, the steps between pain ratings, buying and business fit ratings). A **Try it** calculator shows how a change affects a score.
**Save and re-score all my leads** applies your choices to every analyzed lead straight away, with no new website reading and no AI cost.

**What counts as verified:** something the program measured on the live site (not secure, not mobile-ready, slow, outdated footer, no website on Google),
or something the AI quoted where the program found those exact words on the page. A missing feature or an AI guess is a **suspicion** until you confirm it.
The voice agent is only given verified problems.

**Check a score:** open the page link beside a finding and look for the quoted words. **Copy the evidence pack** pastes the evidence into ChatGPT or Gemini for a second opinion.

**Recalibrating:** Dashboard and Reports show **Results by priority band**. If High priority leads do not get better results than Low ones, change the settings.
Wait for about 30 called leads first. Leads scored with an older method show "old method": select them in Leads and press **Re-analyze**.

## How calling works
- Calls are placed only inside the lead's market calling hours and days.
- A lead is never called if it is on the Do Not Call list, has a bad number or no market, is a sample lead,
  or has a status such as Not Interested, Meeting Booked, Won or Lost.
- The limits in **Calling Rules** apply: calls at once, calls per day, minutes per day.
- Every call opens by saying it is an AI assistant. Settings will not save an opening line without that.
- After each call the program asks Retell for the result every 15 seconds, then sets the outcome from facts first
  (not answered, voicemail, shorter than 15 seconds) and from the transcript for real conversations.

| Outcome | What happens |
|---|---|
| Under 15 seconds, no answer, voicemail | A follow-up is planned 24 hours later. Up to 3 follow-ups, then the lead becomes Unreachable. |
| Callback requested | A callback is planned for the time the person gave, or after the default hours. |
| Meeting booked | Status Meeting Booked, follow-ups stop, a deal is created at the Meeting stage. |
| Interested | Status Interested, follow-ups stop. You take it from there. |
| Not interested, wrong number | The status is updated and follow-ups stop. |
| Asked not to be called | The number goes on Do Not Call and everything for that lead stops. |

The 15 seconds, 3 follow-ups and 24 hours are editable in Settings > Calling Rules. If an outcome was read wrongly,
open the call in Call Logs and set it yourself. The lead and follow-ups update to match.
If the PC was off when a call was due, it is placed when the program runs again, if the market is in its calling hours.

## Your data
Everything is in `%APPDATA%\HYSalesEngine`: `hy_engine.db` (leads, calls, deals), `secret.key` (needed to read your saved API keys: never delete it),
`visuals`, and `backups`. A backup copy is made once a day while the program runs, and Settings > Compliance has **Back up now**.
Copy the backups folder to another drive now and then. To move to a new PC, copy the whole folder.

## What was tested, and what was not
Tested here with automated checks against fake stand-ins for the website, the language model, Google Places and Retell:
first-run account creation, saving and encrypting keys, discovery, CSV and Excel import, duplicates, Do Not Call, the full calling
flow (concurrency limit, outcomes, 24-hour follow-ups, the 3-follow-up chain ending in Unreachable, callbacks, calling hours,
automatic deals), deals and revenue, dashboard figures, reports, visuals and backups. The screens pass a real Next.js build.
The packaging recipe was run here as a Linux program, and that program served every screen and passed the account, keys, import and backup checks.

**Not tested:** the Windows .exe itself (I cannot build for Windows here), real Retell calls, real Google results,
real language model answers, Arabic voices, and how every screen looks in a browser, including the canvas editor.
Expect small things on day one, and test-call yourself first.

## Known limits
- Closing the black window stops the program. Calls and follow-ups only run while it is open.
- The program is not digitally signed, so Windows and some antivirus tools show warnings (see BUILD_WINDOWS.md).
- It replaces the MySQL setup from the proposal with a built-in database file, so there is nothing to install. For one user it is plenty.
  Developers can still set DATABASE_URL to use MySQL.
- Retell field names live in `backend/app/retell.py`, Google fields in `places.py`. If a provider changes something, that is the file to fix.
- Arabic: set a voice and the language code Retell lists for Arabic, then test it. Not verified.
- The United States and Australia each use one time zone for calling hours. Use hours that are safe in every zone.
- Sites that only show content after JavaScript runs may read as empty.
- Scheduled weekly discovery runs, saved filters, custom lead fields, editable scoring weights and custom lead statuses
  from the proposal were not built. Duplicates are matched on phone number and website address.
- Reports are CSV files plus a print page you can save as PDF. Call costs are estimates from the rate you enter.
- Cold calling and AI voices are regulated differently in each country. The program gives you the controls
  (hours, Do Not Call, AI disclosure, recording notice). Confirm the rules for each market before live calls.

## Keep it safe
The program only listens on this computer (127.0.0.1). Do not expose it to the internet. Keep `secret.key` and your backups private.

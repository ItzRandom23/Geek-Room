# PitSense AI 2–3 Minute Demo Script

## 0:00–0:20 — Land on the problem

**Says:** “A driver can say one urgent sentence while the telemetry degrades, but radio review and lap timing usually live apart. PitSense keeps the sentence, vocal signal, and timing evidence together.”

**Clicks:** Open `http://localhost:3000/`.

**Expected:** Hero shows “Hear the signal. Change the lap.” and an explicit demo CTA.

**Backup:** If the browser is slow, use the local landing-page screenshot in the presentation and continue to the direct session URL.

## 0:20–0:35 — Enter the fixture

**Says:** “This is a labelled offline fixture, so the demo does not depend on registration, email, or a model download.”

**Clicks:** **Explore demo session**.

**Expected:** `/sessions?demo=1` redirects to the current seeded session ID; the header says **Explicit demo fixture**.

**Backup:** Navigate to `/sessions`, click **Explore demo**.

## 0:35–0:55 — Establish the signal

**Says:** “The workspace preserves a playable 42-second clip, its source language, and real supplied timing context.”

**Clicks:** Play a few seconds of audio; point to the lap-correlated mode and the urgent evidence card.

**Expected:** Audio player, English source language, 8 real laps, and analysed status.

**Backup:** Skip playback and point to the timestamped transcript; the evidence remains inspectable without sound.

## 0:55–1:35 — Show the hero result

**Says:** “The urgent call is not just a label. It is connected to the original words, confidence, timestamp, and the lap with the greatest time overlap.”

**Clicks:** Select the urgent evidence event; scroll to the report and recommendations.

**Expected:** “Box now, there is smoke and I need a check.”, critical severity, lap context, association notice, and the human-review recommendation.

**Backup:** Use transcript search for `smoke` and select that line.

## 1:35–2:05 — Show impact/history

**Says:** “The report makes the before/after decision visible: radio evidence becomes a review action, and the session is retained for comparison.”

**Clicks:** Open **Analytics** from the top navigation.

**Expected:** Session totals, event count, dominant state, and the demo row with 5 reportable events.

**Backup:** Return to the session and point to the lap summary: median 92.45s, worst 96.4s, and the supplied timing window.

## 2:05–2:30 — Close with technical/business signal

**Says:** “The architecture is Frontend → FastAPI → processing worker → relational report, with optional Redis and object storage. Teams pay for faster review, governed model updates, and private deployment. The important claim is evidence-backed decision support, not diagnosis or causal proof.”

**Clicks:** Open **Methodology** or **JSON** export.

**Expected:** Pipeline explanation or a report download action.

**Backup:** If export is blocked, show the on-screen report; the API export is covered by backend tests.

# Demo script

1. Start the backend and frontend. For the offline judging flow, keep `DEMO_MODE=true`; for real uploads, configure the Hugging Face models and token.
2. Run `python -m app.seed_demo` from `backend` if the fixture is not present.
3. Open the landing page and choose **Open demo session**.
4. Play `demo_radio.wav` in the radio panel. The demo is explicitly labelled as a fixture.
5. Show the transcript timestamps and the stressed/urgent markers.
6. Point to the line chart: laps 4–5 are visibly slower than the session baseline.
7. Click the urgent marker. The audio player seeks to the event and the matching transcript highlights.
8. Read the alert: reduce non-critical radio and investigate the issue before the next run.

The demo audio is self-created and the fixture output is labelled in both the session header and model note.

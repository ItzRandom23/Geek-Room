# Judging pitch

PitSense AI is a silent co-driver for race engineers. It listens to the channel that already exists in a race car, turns it into readable evidence, and puts vocal stress next to the lap where it happened.

Engineers need this because a lap-time delta tells them that something changed, but radio tone and wording often tell them why. PitSense connects those clues without pretending the model proves causation.

Hugging Face is used in the backend for two genuine inference tasks: Whisper speech-to-text and an audio emotion-recognition model for vocal tone. An optional text-emotion model adds a secondary signal. The result is fused with urgency keywords and confidence, then passed through transparent rules.

The technically original part is the synchronized event layer: each radio window can be played, inspected, linked to a transcript segment, mapped to an active lap, and compared with the next lap’s performance. Recommendations are deterministic and auditable.

Limitations are intentionally visible: model quality depends on the radio recording, accent, language, noise, and selected Hugging Face model. The baseline shows associations, not causality, and is not a medical or psychological diagnostic system.

Future work includes team-specific calibration, multi-car comparison, richer telemetry features, multilingual models, and human feedback loops for engineer-confirmed events.

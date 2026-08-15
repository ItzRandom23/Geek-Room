import { describe, expect, it } from "vitest";
import { normalizeManualLaps, validateAudioFile } from "../lib/validation";

describe("audio upload validation", () => {
  it("accepts supported audio within the limit", () => {
    expect(validateAudioFile({name:"radio.wav", size:1000})).toBeNull();
    expect(validateAudioFile({name:"radio.mpeg", size:1000})).toBeNull();
    expect(validateAudioFile({name:"radio.mpga", size:1000})).toBeNull();
  });
  it("rejects executable extensions and oversized files", () => {
    expect(validateAudioFile({name:"radio.exe", size:1000})).toMatch(/WAV/);
    expect(validateAudioFile({name:"radio.wav", size:26 * 1024 * 1024})).toMatch(/25 MB/);
  });
});

describe("manual lap validation", () => {
  it("fills contiguous timestamps without touching the attached audio workflow", () => {
    const result = normalizeManualLaps([
      { lap_number: 1, lap_time_seconds: 90, start_timestamp_seconds: 0, end_timestamp_seconds: 0 },
      { lap_number: 2, lap_time_seconds: 91.5, start_timestamp_seconds: 0, end_timestamp_seconds: 0 },
    ]);
    expect(result.error).toBeNull();
    expect(result.rows[1]).toMatchObject({ start_timestamp_seconds: 90, end_timestamp_seconds: 181.5 });
  });

  it("explains invalid and non-contiguous values before submission", () => {
    expect(normalizeManualLaps([{ lap_number: 1, lap_time_seconds: -4, start_timestamp_seconds: 0, end_timestamp_seconds: 0 }]).error).toMatch(/greater than 0/);
    expect(normalizeManualLaps([
      { lap_number: 1, lap_time_seconds: 90, start_timestamp_seconds: 0, end_timestamp_seconds: 90 },
      { lap_number: 2, lap_time_seconds: 91, start_timestamp_seconds: 95, end_timestamp_seconds: 186 },
    ]).error).toMatch(/previous lap end/);
  });
});

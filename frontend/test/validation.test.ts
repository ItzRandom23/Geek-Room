import { describe, expect, it } from "vitest";
import { validateAudioFile } from "../lib/validation";

describe("audio upload validation", () => {
  it("accepts supported audio within the limit", () => expect(validateAudioFile({name:"radio.wav", size:1000})).toBeNull());
  it("rejects executable extensions and oversized files", () => {
    expect(validateAudioFile({name:"radio.exe", size:1000})).toMatch(/WAV/);
    expect(validateAudioFile({name:"radio.wav", size:26 * 1024 * 1024})).toMatch(/25 MB/);
  });
});

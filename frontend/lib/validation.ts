const allowedAudio = /\.(wav|mp3|m4a|ogg)$/i;
export function validateAudioFile(file: Pick<File, "name"|"size">, maxMb = 25): string | null {
  if (!allowedAudio.test(file.name)) return "Use a WAV, MP3, M4A, or OGG radio clip.";
  if (file.size > maxMb * 1024 * 1024) return `Audio file exceeds the ${maxMb} MB limit.`;
  return null;
}

type EditableLap = { lap_number:number; lap_time_seconds:number; start_timestamp_seconds:number; end_timestamp_seconds:number };

export function normalizeManualLaps(laps: EditableLap[]): { rows: EditableLap[]; error: string | null } {
  const entered = laps.filter((lap) => lap.lap_time_seconds !== 0 || lap.start_timestamp_seconds !== 0 || lap.end_timestamp_seconds !== 0);
  if (!entered.length) return { rows: [], error: "Enter at least one real lap time, or choose audio-only analysis." };
  if (entered.some((lap) => !Number.isFinite(lap.lap_number) || !Number.isInteger(lap.lap_number) || lap.lap_number <= 0)) return { rows: [], error: "Every lap number must be a positive whole number." };
  if (new Set(entered.map((lap) => lap.lap_number)).size !== entered.length) return { rows: [], error: "Lap numbers must be unique." };
  if (entered.some((lap) => !Number.isFinite(lap.lap_time_seconds) || lap.lap_time_seconds <= 0 || lap.lap_time_seconds >= 1000)) return { rows: [], error: "Each lap time must be greater than 0 and less than 1000 seconds." };
  if (entered.some((lap) => !Number.isFinite(lap.start_timestamp_seconds) || !Number.isFinite(lap.end_timestamp_seconds) || lap.start_timestamp_seconds < 0 || lap.end_timestamp_seconds < 0)) return { rows: [], error: "Start and end timestamps cannot be negative." };

  let elapsed = 0;
  const rows: EditableLap[] = [];
  for (const [index, lap] of [...entered].sort((a, b) => a.lap_number - b.lap_number).entries()) {
    const hasStart = lap.start_timestamp_seconds > 0 || index === 0;
    const hasEnd = lap.end_timestamp_seconds > 0;
    const start = hasStart ? lap.start_timestamp_seconds : elapsed;
    const end = hasEnd ? lap.end_timestamp_seconds : start + lap.lap_time_seconds;
    if (end <= start) return { rows: [], error: `Lap ${lap.lap_number}: end time must be after start time.` };
    if (index > 0 && Math.abs(start - elapsed) > 0.001) return { rows: [], error: `Lap ${lap.lap_number}: start time must equal the previous lap end (${elapsed.toFixed(3)}s).` };
    if (Math.abs((end - start) - lap.lap_time_seconds) > 0.05) return { rows: [], error: `Lap ${lap.lap_number}: end minus start must match the lap time.` };
    rows.push({ ...lap, start_timestamp_seconds: start, end_timestamp_seconds: end });
    elapsed = end;
  }
  return { rows, error: null };
}

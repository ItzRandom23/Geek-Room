const allowedAudio = /\.(wav|mp3|m4a|ogg)$/i;
export function validateAudioFile(file: Pick<File, "name"|"size">, maxMb = 25): string | null {
  if (!allowedAudio.test(file.name)) return "Use a WAV, MP3, M4A, or OGG radio clip.";
  if (file.size > maxMb * 1024 * 1024) return `Audio file exceeds the ${maxMb} MB limit.`;
  return null;
}

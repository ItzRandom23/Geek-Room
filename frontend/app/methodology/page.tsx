import { AudioLines, BrainCircuit, Database, GitCompareArrows, LockKeyhole, type LucideIcon } from "lucide-react";

const cards: { icon: LucideIcon; title: string; copy: string }[] = [
  { icon: AudioLines, title: "Multilingual speech-to-text", copy: "Multilingual Whisper runs in the FastAPI backend, detects the spoken language automatically, and returns a complete transcript plus timestamped chunks where the model provides them." },
  { icon: BrainCircuit, title: "Audio emotion", copy: "A Hugging Face audio-classification model is the primary, language-independent tone signal. The clip is evaluated in overlapping windows." },
  { icon: GitCompareArrows, title: "Fusion and correlation", copy: "Audio scores are normalized to six application labels. Optional text emotion, urgency keywords, and confidence adjust the event score; high-stress windows are mapped to the active lap and its successor." },
  { icon: Database, title: "Deterministic report", copy: "Rules compare affected laps with the session median, flag deterioration, and produce recommendations. They show association, not causation." },
  { icon: LockKeyhole, title: "Privacy", copy: "Audio stays in the backend storage directory. No external LLM is used. Delete a session to remove its audio and related database records." },
];

export default function Methodology() {
  return (
    <main className="mx-auto max-w-6xl px-6 py-12">
      <header className="reveal border-b border-white/[0.07] pb-9">
      <div className="section-badge">System notes / methodology</div>
      <h1 className="mt-5 text-4xl font-bold">Transparent by design.</h1>
      <p className="mt-4 max-w-3xl text-lg leading-8 text-slate-400">
        PitSense AI keeps the signal chain inspectable: model output is stored with raw labels and confidence, and the final engineering action comes from documented deterministic rules.
      </p>
      </header>
      <div className="mt-8 grid gap-4 md:grid-cols-2">
        {cards.map(({ icon: Icon, title, copy }, index) => (
          <article className="glass-card glass-edge reveal overflow-hidden p-6" style={{ animationDelay: `${index * 70}ms` }} key={title}>
            <span className="flex h-10 w-10 items-center justify-center rounded-lg border border-cyan/20 bg-cyan/[0.07]"><Icon className="text-cyan" size={19} /></span>
            <h2 className="mt-5 text-lg font-semibold">{title}</h2>
            <p className="mt-2 text-sm leading-6 text-slate-400">{copy}</p>
          </article>
        ))}
      </div>
      <div className="panel mt-5 p-6 md:flex md:items-start md:justify-between md:gap-10">
        <div>
        <div className="section-badge">Application labels</div>
        <div className="mt-4 flex flex-wrap gap-2">
          {["calm", "stressed", "tired", "frustrated", "urgent", "uncertain"].map(label => (
            <span className="chip border-white/15 bg-white/5 text-slate-300 capitalize" key={label}>{label}</span>
          ))}
        </div>
        </div>
        <p className="mt-5 max-w-xl text-sm leading-6 text-slate-400 md:mt-1">
          Raw model labels such as neutral, fear, anger, sadness, or surprise are retained for transparency and mapped to the application vocabulary. Low confidence results surface “Manual review recommended.”
        </p>
      </div>
    </main>
  );
}

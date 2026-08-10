import { AlertTriangle, CheckCircle2, CircleDashed, Loader2, ShieldAlert } from "lucide-react";

export function Button({ children, className = "", ...props }: { children: React.ReactNode; className?: string; [key: string]: unknown }) {
  return <button className={`btn-glow ${className}`} {...props}>{children}</button>;
}

export function GhostButton({ children, className = "", ...props }: { children: React.ReactNode; className?: string; [key: string]: unknown }) {
  return <button className={`btn-ghost ${className}`} {...props}>{children}</button>;
}

export function Badge({ children, tone = "slate" }: { children: React.ReactNode; tone?: string }) {
  const tones: Record<string, string> = {
    slate: "border-white/15 bg-white/5 text-slate-300",
    orange: "border-[rgba(255,107,0,0.4)] bg-[rgba(255,107,0,0.12)] text-[#FF6B00]",
    cyan: "border-[rgba(0,240,255,0.4)] bg-[rgba(0,240,255,0.1)] text-cyan",
    amber: "border-amber-400/40 bg-amber-400/10 text-amber-300",
    green: "border-emerald-400/40 bg-emerald-400/10 text-emerald-300",
  };
  return <span className={`chip ${tones[tone] || tones.slate}`}>{children}</span>;
}

export function StatusIcon({ status }: { status: string }) {
  if (status === "analysing") return <Loader2 className="animate-spin text-amber" size={16} />;
  if (status === "analysed") return <CheckCircle2 className="text-emerald-400" size={16} />;
  if (status === "error") return <AlertTriangle className="text-signal" size={16} />;
  return <CircleDashed className="text-slate-500" size={16} />;
}

export function ErrorBox({ message }: { message: string }) {
  return (
    <div role="alert" className="flex gap-3 rounded-lg border border-[rgba(255,92,26,0.35)] bg-[rgba(255,92,26,0.1)] p-4 text-sm text-red-100 shadow-[0_0_20px_rgba(255,61,0,0.12)]">
      <ShieldAlert size={18} className="mt-0.5 shrink-0 text-signal" />
      <span>{message}</span>
    </div>
  );
}

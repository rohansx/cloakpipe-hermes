import React from "react";
import { AbsoluteFill, Audio, Freeze, OffthreadVideo, Sequence, interpolate, staticFile, useCurrentFrame } from "remotion";

// Real recording of `hermes` with the plugin enabled (asciinema → agg → ffmpeg, idle capped at 1.5s).
// Each scene plays a slice of that recording, then freezes on its last frame until the narration ends.

export const FPS = 30;
const sec = (s: number) => Math.round(s * FPS);
const BG = "#0b0d10", FG = "#e6e6e6", DIM = "#8a919c", GOLD = "#e0a94a";
const COLORS = { ALLOW: "#3fb950", DENY: "#f85149", HOLD: "#e0a94a", INFO: "#8a919c" } as const;
const MONO = "ui-monospace, 'JetBrains Mono', Menlo, monospace";
const SANS = "Inter, 'Helvetica Neue', Arial, sans-serif";

type Verdict = keyof typeof COLORS;
type Scene = { id: string; from: number; to: number; vo: number; verdict: Verdict; label: string; caption: string };

// from/to: seconds in terminal.mp4 (see scratch marks.py). vo: narration length in seconds.
const SCENES: Scene[] = [
  { id: "status",  from: 3.0,   to: 6.36,  vo: 8.7,  verdict: "INFO",  label: "gate status",            caption: "/cloakpipe status: enforce mode, six tools under contract, signed event log" },
  { id: "ls",      from: 6.36,  to: 14.72, vo: 7.2,  verdict: "ALLOW", label: "ls ~/orca",              caption: "A plain command. Arguments checked, call admitted, outcome recorded." },
  { id: "pipe",    from: 14.72, to: 22.68, vo: 10.7, verdict: "DENY",  label: "curl … | sh",            caption: "Rule no-pipe-to-shell. Refused on the exact arguments, with the reason." },
  { id: "creds",   from: 22.68, to: 31.55, vo: 5.8,  verdict: "DENY",  label: "read .aws/credentials", caption: "Rule no-credential-files." },
  { id: "selfmod", from: 31.55, to: 43.42, vo: 5.5,  verdict: "DENY",  label: "write config.yaml", caption: "Rule no-self-modification. The agent cannot edit its own config." },
  { id: "sudo",    from: 43.42, to: 68.5,  vo: 11.9, verdict: "HOLD",  label: "sudo -n true",           caption: "Held for a human. Hermes's prompt carries CloakPipe's fingerprint; approving runs this call once." },
  { id: "verify",  from: 92.5,  to: 98.3,  vo: 8.3,  verdict: "INFO",  label: "/cloakpipe verify",      caption: "Signed, hash-chained ledger verified offline. Result: OK." },
];
const INTRO = 12.5, OUTRO = 7.5;
const sceneLen = (s: Scene) => Math.max(s.to - s.from, s.vo + 1.0);
export const totalFrames = sec(INTRO + SCENES.reduce((a, s) => a + sceneLen(s), 0) + OUTRO);

const fadeIn = (frame: number, start: number, len = 12) =>
  interpolate(frame, [start, start + len], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });

const Card: React.FC<{ title: string; lines: string[]; small?: string }> = ({ title, lines, small }) => {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill style={{ background: BG, color: FG, fontFamily: SANS, justifyContent: "center", alignItems: "center", padding: 160, textAlign: "center" }}>
      <div style={{ fontSize: 84, fontWeight: 700, letterSpacing: -1.5, opacity: fadeIn(frame, 0) }}>{title}</div>
      {lines.map((l, i) => <div key={i} style={{ fontSize: 40, color: DIM, marginTop: i ? 18 : 40, opacity: fadeIn(frame, 20 + i * 14) }}>{l}</div>)}
      {small && <div style={{ fontSize: 28, color: GOLD, marginTop: 56, fontFamily: MONO, opacity: fadeIn(frame, 50) }}>{small}</div>}
    </AbsoluteFill>
  );
};

const Terminal: React.FC<{ scene: Scene; index: number }> = ({ scene, index }) => {
  const frame = useCurrentFrame();
  const play = sec(scene.to - scene.from);
  const video = <OffthreadVideo src={staticFile("terminal.mp4")} startFrom={sec(scene.from)} style={{ width: "100%", height: "100%", objectFit: "contain" }} muted />;
  return (
    <AbsoluteFill style={{ background: BG, color: FG, fontFamily: MONO }}>
      <div style={{ position: "absolute", top: 34, left: 90, right: 90, display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: 26, color: DIM }}>
        <span>hermes · claude-sonnet-5-5 · plugin: cloakpipe (enforce) · live recording</span>
        <span style={{ display: "flex", alignItems: "center", gap: 18 }}>
          <span style={{ color: FG }}>{scene.label}</span>
          <span style={{ background: COLORS[scene.verdict], color: BG, fontWeight: 700, padding: "6px 16px", borderRadius: 8, opacity: fadeIn(frame, 6) }}>{scene.verdict}</span>
          <span>{index + 1}/{SCENES.length}</span>
        </span>
      </div>
      <div style={{ position: "absolute", top: 90, left: 90, right: 90, bottom: 150, border: `1px solid #22262c`, borderRadius: 12, overflow: "hidden", background: "#272822" }}>
        {frame < play ? video : <Freeze frame={play - 1}>{video}</Freeze>}
      </div>
      <div style={{ position: "absolute", bottom: 56, left: 90, right: 90, fontFamily: SANS, fontSize: 34, color: COLORS[scene.verdict] === COLORS.INFO ? FG : COLORS[scene.verdict], opacity: fadeIn(frame, 10) }}>
        {scene.caption}
      </div>
      <Audio src={staticFile(`vo/${scene.id}.wav`)} />
    </AbsoluteFill>
  );
};

export const Live: React.FC = () => {
  let at = 0;
  const seq = (len: number, el: React.ReactNode, key: string) => {
    const node = <Sequence key={key} from={sec(at)} durationInFrames={sec(len)}>{el}</Sequence>;
    at += len;
    return node;
  };
  return (
    <AbsoluteFill style={{ background: BG }}>
      {seq(INTRO, <><Card title="CloakPipe for Hermes Agent" lines={["Argument-level policy on every tool call.", "Approvals bound to the exact call. A signed ledger you can verify offline."]} /><Audio src={staticFile("vo/intro.wav")} /></>, "intro")}
      {SCENES.map((s, i) => seq(sceneLen(s), <Terminal scene={s} index={i} />, s.id))}
      {seq(OUTRO, <><Card title="hermes plugins install cloakpipe" lines={["Six-tool starter contract. Generator for all 73 tools.", "Shadow mode to learn. Enforce mode to ship."]} small="github.com/rohansx/cloakpipe-hermes" /><Audio src={staticFile("vo/outro.wav")} /></>, "outro")}
    </AbsoluteFill>
  );
};

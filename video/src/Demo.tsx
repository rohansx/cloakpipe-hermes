import React from "react";
import { AbsoluteFill, Sequence, interpolate, useCurrentFrame, spring, useVideoConfig } from "remotion";
import { scenes, verify, Scene } from "./transcript";

export const FPS = 30;
const sec = (s: number) => Math.round(s * FPS);

// Timeline, in seconds.
const TITLE = 4, PROBLEM = 7, SCENE = 11, VERIFY = 9, IMPACT = 9, END = 5;
export const totalFrames = sec(TITLE + PROBLEM + SCENE * scenes.length + VERIFY + IMPACT + END);

const BG = "#0b0d10", FG = "#e6e6e6", DIM = "#8a919c", GOLD = "#e0a94a";
const COLORS = { ALLOW: "#3fb950", DENY: "#f85149", HOLD: "#e0a94a" } as const;
const MONO = "ui-monospace, 'JetBrains Mono', 'Fira Code', Menlo, monospace";
const SANS = "Inter, 'Helvetica Neue', Arial, sans-serif";

const fadeIn = (frame: number, start: number, len = 12) =>
  interpolate(frame, [start, start + len], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });

const typed = (text: string, frame: number, start: number, cps = 2.2) =>
  text.slice(0, Math.max(0, Math.floor((frame - start) * cps)));

const Card: React.FC<{ title: string; lines?: string[]; small?: string }> = ({ title, lines = [], small }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const pop = spring({ frame, fps, config: { damping: 14 } });
  return (
    <AbsoluteFill style={{ background: BG, color: FG, fontFamily: SANS, justifyContent: "center", alignItems: "center", padding: 160 }}>
      <div style={{ transform: `scale(${0.96 + pop * 0.04})`, opacity: fadeIn(frame, 0), textAlign: "center", maxWidth: 1500 }}>
        <div style={{ fontSize: 84, fontWeight: 700, letterSpacing: -1.5, lineHeight: 1.1 }}>{title}</div>
        {lines.map((l, i) => (
          <div key={i} style={{ fontSize: 40, color: DIM, marginTop: i === 0 ? 40 : 18, opacity: fadeIn(frame, 20 + i * 14) }}>{l}</div>
        ))}
        {small && <div style={{ fontSize: 28, color: GOLD, marginTop: 56, fontFamily: MONO, opacity: fadeIn(frame, 50) }}>{small}</div>}
      </div>
    </AbsoluteFill>
  );
};

const Badge: React.FC<{ verdict: Scene["verdict"]; at: number }> = ({ verdict, at }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const s = spring({ frame: frame - at, fps, config: { damping: 10, stiffness: 160 } });
  if (frame < at) return null;
  return (
    <span style={{
      display: "inline-block", transform: `scale(${s})`, background: COLORS[verdict], color: BG,
      fontFamily: MONO, fontWeight: 700, fontSize: 30, padding: "6px 18px", borderRadius: 8, marginLeft: 24,
    }}>{verdict}</span>
  );
};

const Terminal: React.FC<{ scene: Scene; index: number }> = ({ scene, index }) => {
  const frame = useCurrentFrame();
  const T_PROMPT = 10, T_TOOL = T_PROMPT + Math.ceil(scene.prompt.length / 2.2) + 12, T_BADGE = T_TOOL + 30, T_REPLY = T_BADGE + 14;
  return (
    <AbsoluteFill style={{ background: BG, color: FG, fontFamily: MONO, padding: "70px 110px" }}>
      <div style={{ color: DIM, fontSize: 26, display: "flex", justifyContent: "space-between" }}>
        <span>hermes · claude-sonnet-5-5 · plugin: cloakpipe (enforce)</span>
        <span>{index + 1} / {scenes.length}</span>
      </div>
      <div style={{ marginTop: 60, fontSize: 36, lineHeight: 1.5 }}>
        <span style={{ color: GOLD }}>› </span>{typed(scene.prompt, frame, T_PROMPT)}
        {frame < T_TOOL && <span style={{ opacity: frame % 20 < 10 ? 1 : 0 }}>▍</span>}
      </div>
      <div style={{ marginTop: 40, fontSize: 32, color: DIM, opacity: fadeIn(frame, T_TOOL) }}>
        ⚙ tool call: <span style={{ color: FG }}>{scene.tool}</span>
      </div>
      <div style={{ marginTop: 28, fontSize: 32, opacity: fadeIn(frame, T_BADGE), display: "flex", alignItems: "center" }}>
        <span style={{ color: DIM }}>cloakpipe /decide →</span><Badge verdict={scene.verdict} at={T_BADGE} />
      </div>
      <div style={{ marginTop: 44, borderLeft: `4px solid ${COLORS[scene.verdict]}`, paddingLeft: 30, opacity: fadeIn(frame, T_REPLY, 18) }}>
        <div style={{ color: GOLD, fontSize: 28, marginBottom: 14 }}>☤ Hermes</div>
        <div style={{ fontSize: 30, lineHeight: 1.45, whiteSpace: "pre-wrap", maxWidth: 1600 }}>{scene.reply}</div>
      </div>
      <div style={{ position: "absolute", bottom: 70, left: 110, right: 110, fontFamily: SANS, fontSize: 34, color: COLORS[scene.verdict], opacity: fadeIn(frame, T_REPLY + 30, 20) }}>
        {scene.note}
      </div>
    </AbsoluteFill>
  );
};

const Verify: React.FC = () => {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill style={{ background: BG, color: FG, fontFamily: MONO, padding: "70px 110px" }}>
      <div style={{ fontSize: 36 }}><span style={{ color: GOLD }}>› </span>{typed("/cloakpipe verify", frame, 10, 1.5)}</div>
      <div style={{ marginTop: 40, fontSize: 31, lineHeight: 1.5, whiteSpace: "pre-wrap", color: FG }}>{typed(verify, frame, 35, 6)}</div>
      <div style={{ position: "absolute", bottom: 70, left: 110, right: 110, fontFamily: SANS, fontSize: 34, color: GOLD, opacity: fadeIn(frame, 150, 20) }}>
        Every decision above is in a signed, hash-chained ledger. Anyone can verify it offline with the public key.
      </div>
    </AbsoluteFill>
  );
};

const Impact: React.FC = () => {
  const frame = useCurrentFrame();
  const cols = [
    ["73", "Hermes tools under a deny-by-default contract"],
    ["0", "calls run ungated: if the gate is down, nothing runs"],
    ["1", "fingerprint per approval, bound to the exact arguments"],
  ];
  return (
    <AbsoluteFill style={{ background: BG, color: FG, fontFamily: SANS, padding: "120px 140px" }}>
      <div style={{ fontSize: 64, fontWeight: 700, opacity: fadeIn(frame, 0) }}>What changes with CloakPipe on</div>
      <div style={{ display: "flex", gap: 60, marginTop: 90 }}>
        {cols.map(([n, t], i) => (
          <div key={i} style={{ flex: 1, opacity: fadeIn(frame, 20 + i * 18), borderTop: `4px solid ${GOLD}`, paddingTop: 30 }}>
            <div style={{ fontSize: 140, fontWeight: 700, fontFamily: MONO, color: GOLD, lineHeight: 1 }}>{n}</div>
            <div style={{ fontSize: 36, color: DIM, marginTop: 24, lineHeight: 1.35 }}>{t}</div>
          </div>
        ))}
      </div>
      <div style={{ fontSize: 36, color: FG, marginTop: 90, lineHeight: 1.5, opacity: fadeIn(frame, 90, 20) }}>
        Other guards classify a call by category and ask the model what it meant.
        CloakPipe reads the arguments, applies a contract you wrote, and signs what it decided.
      </div>
    </AbsoluteFill>
  );
};

export const Demo: React.FC = () => {
  let at = 0;
  const seq = (len: number, el: React.ReactNode, key: string) => {
    const node = <Sequence key={key} from={sec(at)} durationInFrames={sec(len)}>{el}</Sequence>;
    at += len;
    return node;
  };
  return (
    <AbsoluteFill style={{ background: BG }}>
      {seq(TITLE, <Card title="CloakPipe for Hermes Agent" lines={["Argument-level policy on every tool call.", "Approvals bound to the exact call. A signed ledger you can verify offline."]} />, "title")}
      {seq(PROBLEM, <Card title="An agent with a terminal will eventually be asked to do something it should not." lines={["A prompt injection, a hallucinated path, a helpful shortcut.", "Category guards ask the model what it meant. We check what it actually passed."]} />, "problem")}
      {scenes.map((s, i) => seq(SCENE, <Terminal scene={s} index={i} />, s.id))}
      {seq(VERIFY, <Verify />, "verify")}
      {seq(IMPACT, <Impact />, "impact")}
      {seq(END, <Card title="hermes plugins install cloakpipe" lines={["Six-tool starter contract. Generator for all 73 tools.", "Shadow mode to learn. Enforce mode to ship."]} small="github.com/rohansx/cloakpipe-hermes" />, "end")}
    </AbsoluteFill>
  );
};

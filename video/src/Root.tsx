import { Composition } from "remotion";
import { Demo, FPS, totalFrames } from "./Demo";
import { Live, totalFrames as liveFrames } from "./Live";

export const Root = () => (
  <>
    {/* Real Hermes recording with voiceover: the hackathon demo. */}
    <Composition id="CloakPipeDemo" component={Live} durationInFrames={liveFrames} fps={FPS} width={1920} height={1080} />
    {/* Typed-out transcript version, no audio. */}
    <Composition id="CloakPipeCards" component={Demo} durationInFrames={totalFrames} fps={FPS} width={1920} height={1080} />
  </>
);

import {
  makeProject,
  waitFor,
  Vector2,
  createRef,
  ThreadGenerator,
  sequence,
} from "@revideo/core";
import { Rect, Video, makeScene2D, Media } from "@revideo/2d";
import "./global.css";
import data from "./detection.json";

interface Detection {
  position: [number, number];
  size: [number, number];
  color: string;
}

interface DetectionGroup {
  detections: Detection[];
  duration: number;
  start: number;
  end: number;
  key: number;
}

function getCumulativeTime(currentIndex: number): number {
  let totalTime = 0;
  for (let i = 0; i < currentIndex; i++) {
    totalTime += detections[i].duration;
  }
  return totalTime;
}

const detections: DetectionGroup[] = data.groups as DetectionGroup[];
const scene = makeScene2D("scene", function* (view): ThreadGenerator {
  const layoutSize: [number, number] = [1080, 1920];
  const videoSize: [number, number] = [
    (data.original_width / data.original_height) * 1920,
    1920,
  ];

  // Create two permanent video references
  const video1 = createRef<Media>();
  const video2 = createRef<Media>();
  const _layoutRef = createRef<Rect>();

  // Create containers for the videos
  const container1 = createRef<Rect>();
  const container2 = createRef<Rect>();

  const baseLayout = (
    <Rect
      ref={_layoutRef}
      size={layoutSize}
      clip={true}
      fill={"black"}
      position={Vector2.zero}
    >
      <Rect
        ref={container1}
        size={layoutSize}
        clip={true}
        fill={"black"}
        position={Vector2.zero}
      >
        <Video
          ref={video1}
          size={videoSize}
          // src={"http://localhost:9000/fast.mp4"}
          src={
            "https://9000-mboneamjema-vividcutai-la8bzjch1jc.ws-eu117.gitpod.io/speed.mp4"
          }
          // play={true}
        />
      </Rect>
      <Rect
        ref={container2}
        size={layoutSize}
        clip={true}
        fill={"black"}
        position={Vector2.zero}
      >
        <Video
          ref={video2}
          size={videoSize}
          // src={"http://localhost:9000/fast.mp4"}

          src={
            "https://9000-mboneamjema-vividcutai-la8bzjch1jc.ws-eu117.gitpod.io/speed.mp4"
          }
          // play={true}
        />
      </Rect>
    </Rect>
  );

  yield view.add(baseLayout);
  video1().clampTime(0);
  video2().clampTime(0);
  for (const group of detections) {
    const groupIndex = detections.indexOf(group);
    const isSplitScreen = group.detections.length === 2;
    const startTime = group.start;

    // Reset layout opacity
    yield* _layoutRef().opacity(1, 0);

    // Configure containers and videos based on current group
    if (isSplitScreen) {
      // Setup for split screen
      container1().size([layoutSize[0], layoutSize[1] / 2]);
      container2().size([layoutSize[0], layoutSize[1] / 2]);

      container1().position(new Vector2(0, -layoutSize[1] / 4));
      container2().position(new Vector2(0, layoutSize[1] / 4));

      container2().opacity(1);
    } else {
      // Setup for single video
      container1().size(layoutSize);
      container1().position(Vector2.zero);
      container2().opacity(0);
    }

    // Set video times
    video1().clampTime(startTime);
    video2().clampTime(startTime);

    // Update video positions to center detections
    const detection1 = group.detections[0];
    yield* video1().position(
      new Vector2(-detection1.position[0], -detection1.position[1]),
      0
    );

    if (isSplitScreen && group.detections[1]) {
      const detection2 = group.detections[1];
      yield* video2().position(
        new Vector2(-detection2.position[0], -detection2.position[1]),
        0
      );
    }

    video1().play();
    video2().play();

    // Wait for the specified duration

    yield* waitFor(group.duration);

    // Fade out
    yield* _layoutRef().opacity(0, 0);
  }
});

export default makeProject({
  scenes: [scene],
  settings: {
    shared: {
      size: { x: 1080, y: 1920 },
    },
  },
});

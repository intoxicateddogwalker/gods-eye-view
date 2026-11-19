// Futuristic motion: slow idle auto-rotation of the globe.
//
// The globe turns slowly while nobody is interacting with it, and the
// rotation pauses the moment the user (or the app, for example during a
// fly-to) moves the camera. Panel depth, pulsing markers, flowing motion
// and the boot intro live in src/ui/styles/hud-animations.css; this
// module only drives the rotation, which needs the Cesium camera.
//
// The app exposes its viewer for diagnostics/QA as
// window.__godsEyeView.viewer (the same handle its own QA scripts use),
// and Cesium is available as the window.Cesium global that the injected
// Cesium.js script defines. Both are checked before use, so this module
// is a no-op if either is ever unavailable, and it never touches the
// app's own camera verbs. Selecting a layer or contact already flies
// the camera smoothly through the app's eased fly-to, and this rotation
// stands down while any such flight is in progress.
//
// Rotation is driven by a short interval timer, not by animation
// frames: animation frames can be throttled or paused entirely while a
// tab is in the background or occluded, which would stall the globe.
// Each tick is credited by the true elapsed time, so the globe turns at
// the same speed however often the timer fires. All idle timing uses
// performance.now().

if (typeof document !== 'undefined' && typeof window !== 'undefined') {
  const prefersReducedMotion =
    typeof window.matchMedia === 'function' &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  if (!prefersReducedMotion) {
    // One full turn takes about twelve minutes: slow, smooth, ambient.
    const ROTATION_DEGREES_PER_SECOND = 0.5;
    const ROTATION_INTERVAL_MILLISECONDS = 100;
    const MAX_STEP_SECONDS = 1;
    const IDLE_MILLISECONDS = 10000;
    const STARTUP_DELAY_MILLISECONDS = 3000;
    const POLL_INTERVAL_MILLISECONDS = 500;
    const POLL_TIMEOUT_MILLISECONDS = 300000;
    // One tick of our own rotation moves the camera only a few
    // kilometres at globe height; anything moving much faster than
    // that is the user or the app, so the rotation stands down.
    const EXTERNAL_MOVE_METERS = 20000;

    let lastInteraction = performance.now();
    let lastCameraPosition = null;
    let lastTick = 0;
    let rotationFailed = false;
    let rotationTimer = 0;

    const markInteraction = () => {
      lastInteraction = performance.now();
    };

    ['pointerdown', 'wheel', 'touchstart', 'keydown'].forEach((type) => {
      document.addEventListener(type, markInteraction, { passive: true });
    });
    document.addEventListener('visibilitychange', markInteraction);

    const getViewer = () => {
      const exposed = window.__godsEyeView;
      const viewer = exposed ? exposed.viewer : null;
      if (!viewer || !viewer.scene || !viewer.scene.camera) return null;
      if (typeof window.Cesium === 'undefined') return null;
      return viewer;
    };

    const rotateStep = () => {
      if (rotationFailed) return;
      try {
        const viewer = getViewer();
        if (!viewer) return;
        const now = performance.now();
        const deltaSeconds = Math.min((now - lastTick) / 1000, MAX_STEP_SECONDS);
        lastTick = now;
        if (document.visibilityState === 'hidden') return;
        if (now - lastInteraction < IDLE_MILLISECONDS) {
          lastCameraPosition = viewer.scene.camera.position.clone();
          return;
        }
        const Cesium = window.Cesium;
        const camera = viewer.scene.camera;
        const current = camera.position.clone();
        if (lastCameraPosition) {
          const moved = Cesium.Cartesian3.distance(current, lastCameraPosition);
          if (moved > EXTERNAL_MOVE_METERS) {
            lastInteraction = now;
            lastCameraPosition = current;
            return;
          }
        }
        const cartographic = Cesium.Cartographic.fromCartesian(current);
        const nextLongitude =
          cartographic.longitude +
          Cesium.Math.toRadians(ROTATION_DEGREES_PER_SECOND * deltaSeconds);
        camera.setView({
          destination: Cesium.Cartesian3.fromRadians(
            nextLongitude,
            cartographic.latitude,
            cartographic.height,
          ),
          orientation: {
            heading: camera.heading,
            pitch: camera.pitch,
            roll: camera.roll,
          },
        });
        lastCameraPosition = camera.position.clone();
      } catch (error) {
        rotationFailed = true;
        if (rotationTimer) window.clearInterval(rotationTimer);
        console.warn('Idle globe rotation disabled:', error);
      }
    };

    const startPolling = () => {
      const startedAt = Date.now();
      const poll = () => {
        if (rotationFailed) return;
        if (getViewer()) {
          lastTick = performance.now();
          window.setTimeout(() => {
            lastInteraction = performance.now();
            rotationTimer = window.setInterval(
              rotateStep,
              ROTATION_INTERVAL_MILLISECONDS,
            );
          }, STARTUP_DELAY_MILLISECONDS);
          return;
        }
        if (Date.now() - startedAt < POLL_TIMEOUT_MILLISECONDS) {
          window.setTimeout(poll, POLL_INTERVAL_MILLISECONDS);
        }
      };
      poll();
    };

    startPolling();
  }
}

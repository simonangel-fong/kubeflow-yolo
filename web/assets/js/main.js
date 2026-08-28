/* Active nav link on scroll */
const sections = document.querySelectorAll("section[id]");
const navLinks = document.querySelectorAll("#mainNav .nav-link[href^='#']");

const observer = new IntersectionObserver(
  (entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        navLinks.forEach((l) => l.classList.remove("active"));
        const active = document.querySelector(
          `#mainNav .nav-link[href="#${entry.target.id}"]`
        );
        if (active) active.classList.add("active");
      }
    });
  },
  { rootMargin: "-40% 0px -55% 0px" }
);

sections.forEach((s) => observer.observe(s));

/* Demo video: autoplay muted, but only while it is actually on screen.
   A bare autoplay attribute would pull the whole file on page load, so the
   source is left unloaded until the section is scrolled into view. */
const demo = document.getElementById("demoVideo");

if (demo) {
  // Autoplay is only permitted while muted; keep this true regardless of markup.
  demo.muted = true;

  // Set while the observer is the one pausing, so its own pause event is not
  // mistaken for the viewer pressing pause.
  let pausingOffscreen = false;
  let userPaused = false;

  demo.addEventListener("pause", () => {
    // The pause event is delivered asynchronously, so the flag is cleared here
    // rather than straight after the pause() call that set it.
    if (pausingOffscreen) {
      pausingOffscreen = false;
    } else {
      userPaused = true;
    }
  });
  demo.addEventListener("play", () => {
    userPaused = false;
  });

  // A short player in a small viewport never reaches a high ratio, so the
  // decision is made from the reported ratio against a low hysteresis pair
  // rather than from a single threshold the element may never cross.
  const PLAY_AT = 0.3;
  const PAUSE_AT = 0.1;

  const videoObserver = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        const ratio = entry.intersectionRatio;

        if (ratio >= PLAY_AT) {
          if (demo.preload === "none") demo.preload = "auto";
          if (!userPaused && demo.paused) {
            // Older browsers return undefined rather than a promise.
            const p = demo.play();
            if (p) p.catch(() => {});
          }
        } else if (ratio <= PAUSE_AT && !demo.paused) {
          pausingOffscreen = true;
          demo.pause();
        }
      });
    },
    // Many steps so the callback keeps firing as the ratio changes.
    { threshold: [0, 0.05, 0.1, 0.2, 0.3, 0.5, 0.75, 1] }
  );

  videoObserver.observe(demo);
}

// Pages: one section is shown at a time; the URL hash selects it (#cover, #approach, #q1, #q2, #q3).
// Content: cards fade in as they enter the viewport.
(function () {
  const nav = document.querySelector(".nav");
  const links = [...document.querySelectorAll("[data-nav]")];
  const pages = [...document.querySelectorAll("main > .page")];
  const ids = pages.map((p) => p.id);

  function show(id) {
    const target = pages.find((p) => p.id === id) || pages[0];
    pages.forEach((p) => { p.hidden = p !== target; });
    links.forEach((a) => {
      const on = a.dataset.nav === target.id;
      a.classList.toggle("is-active", on);
      if (on) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current");
    });
    document.body.dataset.page = target.id;
    target.classList.remove("page--enter");
    void target.offsetWidth;                    // restart the entrance animation
    target.classList.add("page--enter");
    window.scrollTo({ top: 0, behavior: "instant" });
    window.dispatchEvent(new CustomEvent("pagechange", { detail: target.id }));
  }

  window.addEventListener("hashchange", () => show(location.hash.slice(1)));
  show(location.hash.slice(1));

  // Left and right arrow keys move between pages.
  document.addEventListener("keydown", (e) => {
    if (e.target.closest("input, textarea, select, button") || e.altKey || e.ctrlKey || e.metaKey) return;
    const i = ids.indexOf(document.body.dataset.page);
    if (e.key === "ArrowRight" && i < ids.length - 1) location.hash = ids[i + 1];
    if (e.key === "ArrowLeft" && i > 0) location.hash = ids[i - 1];
  });

  const onScroll = () => nav.classList.toggle("is-scrolled", window.scrollY > 24);
  window.addEventListener("scroll", onScroll, { passive: true });
  onScroll();

  const targets = document.querySelectorAll(
    ".page__head, .framework__top > *, .tier, .analysis__head, .kpi, .context > *, .fig, .takeaways > *"
  );
  if (!("IntersectionObserver" in window)) return;
  const reveal = new IntersectionObserver(
    (entries) => {
      entries.forEach((e) => {
        if (e.isIntersecting) {
          e.target.classList.add("is-in");
          reveal.unobserve(e.target);
        }
      });
    },
    { threshold: 0.08 }
  );
  targets.forEach((t) => {
    t.classList.add("reveal");
    reveal.observe(t);
  });
})();

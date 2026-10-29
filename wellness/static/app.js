// Smart Wellness Wearable: interface behaviour only.
// Nothing here sends data anywhere; every check is repeated on the server.
// Text from the page is always written with textContent, never as HTML.
(function () {
  "use strict";
  var reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text) e.textContent = text;
    return e;
  }

  // ---- Toast for small confirmations ----
  var toastBox = el("div", "toasts");
  function toast(text) {
    var t = el("div", "toast", text);
    toastBox.appendChild(t);
    setTimeout(function () { t.classList.add("out"); }, 1800);
    setTimeout(function () { t.remove(); }, 2300);
  }

  // ---- Greeting by time of day and live clock ----
  function greet() {
    var g = document.querySelector("[data-greet]");
    if (!g) return;
    var h = new Date().getHours();
    g.textContent = h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening";
  }
  function tick() {
    var c = document.querySelector("[data-clock]");
    if (!c) return;
    var now = new Date();
    c.textContent = "· " + now.toLocaleDateString("en-GB", { weekday: "long", day: "numeric", month: "long" }) +
      " · " + now.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" });
  }

  // ---- Count-up numbers ----
  function countUp(node) {
    var target = parseFloat(node.getAttribute("data-count"));
    var dec = parseInt(node.getAttribute("data-decimals") || "0", 10);
    if (isNaN(target)) return;
    var fmt = function (v) { return dec ? v.toFixed(dec) : Math.round(v).toLocaleString("en-US"); };
    if (reduceMotion || target === 0) { node.textContent = fmt(target); return; }
    var start = null, dur = 1100;
    function step(ts) {
      if (start === null) start = ts;
      var p = Math.min((ts - start) / dur, 1);
      node.textContent = fmt(target * (1 - Math.pow(1 - p, 3)));
      if (p < 1) requestAnimationFrame(step);
    }
    node.textContent = fmt(0);
    requestAnimationFrame(step);
  }

  // ---- Copy buttons ----
  function copyButtons() {
    document.querySelectorAll("[data-copy]").forEach(function (b) {
      b.addEventListener("click", function () {
        var value = b.getAttribute("data-copy");
        var done = function () {
          b.textContent = "Copied ✓"; b.classList.add("done"); toast("Copied to clipboard");
          setTimeout(function () { b.textContent = "Copy"; b.classList.remove("done"); }, 1600);
        };
        if (navigator.clipboard) navigator.clipboard.writeText(value).then(done, function () {});
      });
    });
  }

  // ---- Notices: slide in, with a close button ----
  function notices() {
    document.querySelectorAll("main > .message, main > .error").forEach(function (n) {
      var x = el("button", "close", "×");
      x.type = "button"; x.setAttribute("aria-label", "Dismiss");
      x.addEventListener("click", function () { n.classList.add("gone"); setTimeout(function () { n.remove(); }, 300); });
      n.appendChild(x);
    });
  }

  // ---- Password fields: show / hide and a strength hint ----
  function passwords() {
    document.querySelectorAll('input[type="password"]').forEach(function (input) {
      var wrap = el("span", "pw");
      input.parentNode.insertBefore(wrap, input);
      wrap.appendChild(input);
      var eye = el("button", "eye", "Show");
      eye.type = "button";
      eye.addEventListener("click", function () {
        var show = input.type === "password";
        input.type = show ? "text" : "password";
        eye.textContent = show ? "Hide" : "Show";
      });
      wrap.appendChild(eye);

      if (input.getAttribute("minlength")) {
        var meter = el("span", "meter"), bar = el("i"), label = el("small", "meter-label", "At least 8 characters");
        meter.appendChild(bar);
        wrap.parentNode.appendChild(meter);
        wrap.parentNode.appendChild(label);
        input.addEventListener("input", function () {
          var v = input.value, score = 0;
          if (v.length >= 8) score++;
          if (v.length >= 12) score++;
          if (/[A-Z]/.test(v) && /[a-z]/.test(v)) score++;
          if (/\d/.test(v)) score++;
          if (/[^A-Za-z0-9]/.test(v)) score++;
          var levels = ["Too short", "Weak", "Fair", "Good", "Strong", "Very strong"];
          if (v.length < 8) score = 0;
          meter.setAttribute("data-level", String(score));
          bar.style.width = (v.length ? Math.max(score, 0.4) / 5 * 100 : 0) + "%";
          label.textContent = v.length ? levels[score] : "At least 8 characters";
        });
      }
    });
  }

  // ---- Contact ID character counter ----
  function counters() {
    document.querySelectorAll("[data-count-chars]").forEach(function (input) {
      var max = input.maxLength, c = el("span", "chars", "0/" + max);
      input.parentNode.insertBefore(c, input.nextSibling);
      input.addEventListener("input", function () {
        c.textContent = input.value.length + "/" + max;
        c.classList.toggle("full", input.value.length === max);
      });
    });
  }

  // ---- Live preview of what a contact will see ----
  function previews() {
    document.querySelectorAll("[data-preview]").forEach(function (p) {
      var form = p.closest("form"), name = p.getAttribute("data-name");
      function update() {
        var chosen = [];
        form.querySelectorAll('input[name="category"]:checked').forEach(function (cb) {
          chosen.push(cb.closest("label").textContent.trim());
        });
        p.textContent = chosen.length
          ? name + " will see: " + chosen.join(", ")
          : name + " will not see any of your data.";
        p.classList.toggle("none", !chosen.length);
      }
      form.addEventListener("change", update);
      update();
    });
  }

  // ---- Chart tooltips (hover or tap) ----
  function tooltips() {
    var tip = el("div", "tip");
    document.body.appendChild(tip);
    document.querySelectorAll("[data-tip]").forEach(function (col) {
      function show() {
        tip.textContent = col.getAttribute("data-tip");
        var r = col.getBoundingClientRect();
        tip.style.left = (r.left + r.width / 2 + window.scrollX) + "px";
        tip.style.top = (r.top + window.scrollY - 8) + "px";
        tip.classList.add("on");
        col.classList.add("active");
      }
      function hide() { tip.classList.remove("on"); col.classList.remove("active"); }
      col.addEventListener("mouseenter", show);
      col.addEventListener("mouseleave", hide);
      col.addEventListener("click", show);
    });
  }

  // ---- Cards appear as they scroll into view ----
  function reveal() {
    var items = document.querySelectorAll("main section, .stat, .hero-text > *");
    if (reduceMotion || !("IntersectionObserver" in window)) return;
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) { e.target.classList.add("shown"); io.unobserve(e.target); }
      });
    }, { threshold: 0.08 });
    items.forEach(function (n, i) {
      n.classList.add("reveal");
      n.style.transitionDelay = Math.min(i * 60, 420) + "ms";
      io.observe(n);
    });
  }

  // ---- Watch illustration follows the pointer ----
  function tilt() {
    var art = document.querySelector("[data-tilt]");
    if (!art || reduceMotion) return;
    window.addEventListener("mousemove", function (e) {
      var x = (e.clientX / window.innerWidth - 0.5), y = (e.clientY / window.innerHeight - 0.5);
      art.style.transform = "perspective(600px) rotateY(" + (x * 16) + "deg) rotateX(" + (-y * 12) + "deg)";
    });
  }

  // ---- Button press ripple and busy state on submit ----
  function buttons() {
    document.addEventListener("pointerdown", function (e) {
      var b = e.target.closest("button, a.button");
      if (!b || reduceMotion) return;
      var r = b.getBoundingClientRect(), s = el("span", "ripple");
      s.style.left = (e.clientX - r.left) + "px";
      s.style.top = (e.clientY - r.top) + "px";
      b.appendChild(s);
      setTimeout(function () { s.remove(); }, 600);
    });
    document.querySelectorAll("form").forEach(function (f) {
      f.addEventListener("submit", function () {
        var b = f.querySelector("button:not([type=button])");
        if (b) setTimeout(function () { b.classList.add("busy"); }, 0);
      });
    });
    window.addEventListener("pageshow", function () {
      document.querySelectorAll(".busy").forEach(function (b) { b.classList.remove("busy"); });
    });
  }

  // ---- Light / dark mode switch ----
  // My data: changing the day reloads the readings for that day
  function autosubmit() {
    document.querySelectorAll('select[data-autosubmit]').forEach(function (sel) {
      sel.addEventListener('change', function () { sel.form.submit(); });
    });
  }

  function themeToggle() {
    var root = document.documentElement;
    document.querySelectorAll("[data-theme-toggle]").forEach(function (b) {
      b.addEventListener("click", function () {
        var next = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
        root.classList.add("theming");
        root.setAttribute("data-theme", next);
        try { localStorage.setItem("theme", next); } catch (e) {}
        setTimeout(function () { root.classList.remove("theming"); }, 500);
        toast(next === "dark" ? "Dark mode on" : "Light mode on");
      });
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    document.body.appendChild(toastBox);
    document.documentElement.classList.add("js");
    greet(); tick(); setInterval(tick, 15000);
    document.querySelectorAll("[data-count]").forEach(countUp);
    autosubmit(); themeToggle(); copyButtons(); notices(); passwords(); counters(); previews(); tooltips(); reveal(); tilt(); buttons();
  });
})();

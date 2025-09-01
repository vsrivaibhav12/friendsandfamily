// static/app.js
(() => {
  const onReady = (fn) =>
    document.readyState !== "loading"
      ? fn()
      : document.addEventListener("DOMContentLoaded", fn);

  onReady(() => {
    // ---------------- Tabs (data-tab + .tab-content with id="tab-<name>")
    document.querySelectorAll(".tabs").forEach((container) => {
      const tabs = container.querySelectorAll(".tab");
      tabs.forEach((btn) => {
        btn.addEventListener("click", () => {
          tabs.forEach((b) => b.classList.remove("active"));
          btn.classList.add("active");
          const name = btn.dataset.tab;
          document
            .querySelectorAll(".tab-content")
            .forEach(
              (p) => (p.style.display = p.id === "tab-" + name ? "block" : "none")
            );
          // keep URL hash in sync without scrolling
          history.replaceState(null, "", "#" + name);
        });
      });
    });

    // Hash deep-link support (#upi / #cash etc.)
    if (location.hash) {
      const target = document.querySelector(
        `.tab[data-tab="${location.hash.substring(1)}"]`
      );
      if (target) target.click();
    }

    // ---------------- Flash auto-hide
    setTimeout(() => {
      document.querySelectorAll(".flash").forEach((el) => {
        el.classList.add("fadeout");
      });
      setTimeout(() => {
        document.querySelectorAll(".flash.fadeout").forEach((el) => el.remove());
      }, 500);
    }, 3500);

    // ---------------- Print action
    // Add data-action="print" and optional data-print-target="#selector"
    document.addEventListener("click", (e) => {
      const t = e.target.closest('[data-action="print"]');
      if (!t) return;
      e.preventDefault();
      const sel = t.getAttribute("data-print-target");
      if (sel) {
        const elem = document.querySelector(sel);
        if (elem) {
          const css = document.querySelector('link[rel="stylesheet"]');
          const cssHref = css ? css.href : "";
          const win = window.open("", "printwin");
          win.document.write(
            `<html><head><title>Print</title>${
              cssHref ? `<link rel="stylesheet" href="${cssHref}">` : ""
            }</head><body>${elem.outerHTML}</body></html>`
          );
          win.document.close();
          win.focus();
          win.print();
          win.close();
          return;
        }
      }
      window.print();
    });

    // ---------------- Amount totalers
    // Wrap your inputs.amt in a container with data-totaler="totalSpanId"
    document.querySelectorAll("[data-totaler]").forEach((wrapper) => {
      const out = document.getElementById(wrapper.getAttribute("data-totaler"));
      const inputs = wrapper.querySelectorAll("input.amt");
      const recalc = () => {
        let total = 0;
        inputs.forEach((i) => {
          const v = parseFloat(i.value);
          if (!isNaN(v)) total += v;
        });
        if (out) out.textContent = total.toFixed(2);
      };
      inputs.forEach((i) => i.addEventListener("input", recalc));
      recalc();
    });

    // ---------------- Dirty form guard (opt-in)
    // Add data-dirty-guard on a <form> to enable
    document.querySelectorAll("form[data-dirty-guard]").forEach((form) => {
      let dirty = false;
      form.addEventListener("change", () => (dirty = true), { capture: true });
      window.addEventListener("beforeunload", (e) => {
        if (dirty) {
          e.preventDefault();
          e.returnValue = "";
        }
      });
      form.addEventListener("submit", () => {
        dirty = false;
      });
    });

    // ---------------- Bulk select helpers (opt-in)
    // Wrap your list in an element with data-select-scope.
    // Put a master checkbox with data-select-all inside it.
    document.querySelectorAll("[data-select-scope]").forEach((scope) => {
      const all = scope.querySelector("[data-select-all]");
      if (!all) return;
      const boxes = scope.querySelectorAll(
        'input[type="checkbox"][name="student_ids"]'
      );
      all.addEventListener("change", () => {
        boxes.forEach((b) => {
          b.checked = all.checked;
          b.dispatchEvent(new Event("change"));
        });
      });
    });

    // ---------------- Keyboard shortcuts
    document.addEventListener("keydown", (e) => {
      // Focus search
      if (e.key === "/" && !/input|textarea|select/i.test(e.target.tagName)) {
        const q = document.querySelector('input[name="q"], input[type="search"]');
        if (q) {
          q.focus();
          q.select();
          e.preventDefault();
        }
      }
      // Let Ctrl/Cmd+P fall through to browser print
    });
  });
})();

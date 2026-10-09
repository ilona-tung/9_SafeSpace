// Drag-and-drop journal editor.
// Reads the user's rewards from the page (json_script "journal-rewards")
// and, on save, sends the text + layout to Django in the form.

(function () {
  const rewards = JSON.parse(document.getElementById("journal-rewards").textContent);

  const page = document.getElementById("journal-page");
  const frameLayer = document.getElementById("journal-frame");
  const text = document.getElementById("journal-text");
  const tools = document.getElementById("sticker-tools");
  const tray = document.getElementById("sticker-tray");
  const form = document.getElementById("journal-form");

  let placed = [];        // {sticker, x, y, rotation, scale, el}
  let selected = null;
  let topZ = 10;
  const chosen = { background: null, frame: null, font: null };

  // ------------------------------------------------------------
  // Sticker tray (drag from here onto the page)
  // ------------------------------------------------------------
  function renderTray() {
    tray.innerHTML = "";

    if (!rewards.sticker.length) {
      tray.innerHTML = '<p class="tray-hint" style="grid-column: 1 / -1">Complete quests to earn stickers.</p>';
      return;
    }

    rewards.sticker.forEach(function (sticker) {
      const item = document.createElement("div");
      item.className = "tray-sticker" + (sticker.count === 0 ? " empty" : "");
      item.title = sticker.name;

      const img = document.createElement("img");
      img.src = sticker.url;
      img.alt = sticker.name;
      img.draggable = false;

      const count = document.createElement("span");
      count.className = "tray-count";
      count.textContent = sticker.count === null ? "∞" : "×" + sticker.count;

      item.append(img, count);
      item.addEventListener("pointerdown", function (event) {
        if (sticker.count === null || sticker.count > 0) startTrayDrag(event, sticker);
      });
      tray.appendChild(item);
    });
  }

  function startTrayDrag(event, sticker) {
    event.preventDefault();
    const ghost = document.createElement("img");
    ghost.className = "drag-ghost";
    ghost.src = sticker.url;
    ghost.alt = "";
    document.body.appendChild(ghost);

    function move(e) {
      ghost.style.left = e.clientX + "px";
      ghost.style.top = e.clientY + "px";
      page.classList.toggle("drop-target", isOverPage(e));
    }

    function end(e) {
      document.removeEventListener("pointermove", move);
      document.removeEventListener("pointerup", end);
      ghost.remove();
      page.classList.remove("drop-target");

      if (isOverPage(e)) {
        const rect = page.getBoundingClientRect();
        placeSticker(
          sticker,
          (e.clientX - rect.left) / rect.width * 100,
          (e.clientY - rect.top) / rect.height * 100
        );
      }
    }

    move(event);
    document.addEventListener("pointermove", move);
    document.addEventListener("pointerup", end);
  }

  function isOverPage(e) {
    const rect = page.getBoundingClientRect();
    return e.clientX >= rect.left && e.clientX <= rect.right &&
           e.clientY >= rect.top && e.clientY <= rect.bottom;
  }

  // ------------------------------------------------------------
  // Stickers on the page: move, select, rotate, resize, remove
  // ------------------------------------------------------------
  function placeSticker(sticker, x, y) {
    if (sticker.count !== null) sticker.count -= 1;   // unlimited stickers have count null
    renderTray();

    const item = {
      sticker: sticker,
      x: x,
      y: y,
      rotation: Math.round(Math.random() * 20 - 10),
      scale: 1,
      el: document.createElement("img")
    };
    item.el.className = "journal-sticker";
    item.el.src = sticker.url;
    item.el.alt = sticker.name;
    item.el.draggable = false;
    item.el.style.zIndex = ++topZ;
    item.el.addEventListener("pointerdown", function (e) { startMove(e, item); });
    page.appendChild(item.el);
    placed.push(item);
    draw(item);
    select(item);
  }

  function draw(item) {
    item.el.style.left = item.x + "%";
    item.el.style.top = item.y + "%";
    item.el.style.transform = "rotate(" + item.rotation + "deg) scale(" + item.scale + ")";
    if (selected === item) positionTools();
  }

  function startMove(event, item) {
    event.preventDefault();
    event.stopPropagation();
    select(item);
    const rect = page.getBoundingClientRect();
    const offsetX = event.clientX - (rect.left + item.x / 100 * rect.width);
    const offsetY = event.clientY - (rect.top + item.y / 100 * rect.height);

    function move(e) {
      item.x = clamp((e.clientX - offsetX - rect.left) / rect.width * 100, 0, 100);
      item.y = clamp((e.clientY - offsetY - rect.top) / rect.height * 100, 0, 100);
      draw(item);
    }

    function end() {
      document.removeEventListener("pointermove", move);
      document.removeEventListener("pointerup", end);
    }

    document.addEventListener("pointermove", move);
    document.addEventListener("pointerup", end);
  }

  function select(item) {
    placed.forEach(function (p) { p.el.classList.toggle("selected", p === item); });
    selected = item;
    tools.hidden = !item;
    if (item) positionTools();
  }

  function positionTools() {
    const size = 90 * selected.scale;
    tools.style.left = selected.x + "%";
    tools.style.top = "calc(" + selected.y + "% + " + (size / 2 + 12) + "px)";
  }

  tools.addEventListener("pointerdown", function (e) { e.stopPropagation(); });

  tools.addEventListener("click", function (e) {
    const button = e.target.closest("button");
    if (!button || !selected) return;

    const action = button.dataset.action;
    if (action === "rotate-left") selected.rotation -= 15;
    if (action === "rotate-right") selected.rotation += 15;
    if (action === "smaller") selected.scale = Math.max(0.5, +(selected.scale - 0.15).toFixed(2));
    if (action === "bigger") selected.scale = Math.min(2.5, +(selected.scale + 0.15).toFixed(2));
    if (action === "front") selected.el.style.zIndex = ++topZ;
    if (action === "remove") return removeSticker(selected);
    draw(selected);
  });

  function removeSticker(item) {
    item.el.remove();
    placed = placed.filter(function (p) { return p !== item; });
    if (item.sticker.count !== null) item.sticker.count += 1;   // the copy goes back to the tray
    renderTray();
    select(null);
  }

  page.addEventListener("pointerdown", function (e) {
    if (!e.target.closest(".journal-sticker")) select(null);
  });

  document.addEventListener("keydown", function (e) {
    if (!selected || document.activeElement === text) return;
    if (e.key === "Delete" || e.key === "Backspace") {
      e.preventDefault();
      removeSticker(selected);
    }
  });

  // ------------------------------------------------------------
  // Background / frame / font: one choice each
  // ------------------------------------------------------------
  const SLOTS = {
    background: { container: "background-options", none: "Plain paper" },
    frame: { container: "frame-options", none: "No frame" },
    font: { container: "font-options", none: "Regular" }
  };

  function renderOptions(slot) {
    const container = document.getElementById(SLOTS[slot].container);
    container.innerHTML = "";

    [null].concat(rewards[slot]).forEach(function (option) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "tray-option";
      button.setAttribute("aria-pressed", String(chosen[slot] === option));

      const swatch = document.createElement("span");
      swatch.className = "tray-swatch";
      if (option && slot !== "font") swatch.style.backgroundImage = "url('" + option.url + "')";
      if (option && slot === "font") {
        swatch.textContent = "Aa";
        swatch.style.cssText = "display:grid;place-items:center;font-family:'reward-font-" + option.id + "',cursive;font-size:1.1rem";
      }

      const label = document.createElement("span");
      label.textContent = option ? option.name : SLOTS[slot].none;

      button.append(swatch, label);

      if (option) {
        const count = document.createElement("span");
        count.className = "tray-count";
        count.textContent = option.count === null ? "∞" : "×" + option.count;
        button.appendChild(count);
      }

      button.addEventListener("click", function () {
        chosen[slot] = option;
        applyStyle();
        renderOptions(slot);
      });

      container.appendChild(button);
    });
  }

  function applyStyle() {
    page.style.setProperty("--page-bg", chosen.background ? "url('" + chosen.background.url + "')" : "none");

    frameLayer.hidden = !chosen.frame;
    frameLayer.style.borderImageSource = chosen.frame ? "url('" + chosen.frame.url + "')" : "none";

    page.classList.toggle("has-font", !!chosen.font);
    if (chosen.font) page.style.setProperty("--page-font", "'reward-font-" + chosen.font.id + "'");
  }

  // ------------------------------------------------------------
  // Save: copy the text and layout into the Django form
  // ------------------------------------------------------------
  form.addEventListener("submit", function () {
    form.elements.content.value = text.innerText.trim();
    form.elements.layout.value = JSON.stringify({
      background: chosen.background ? chosen.background.id : null,
      frame: chosen.frame ? chosen.frame.id : null,
      font: chosen.font ? chosen.font.id : null,
      stickers: placed
        .slice()
        .sort(function (a, b) { return a.el.style.zIndex - b.el.style.zIndex; })
        .map(function (p) {
          return {
            reward: p.sticker.id,
            x: +p.x.toFixed(2),
            y: +p.y.toFixed(2),
            rotation: p.rotation,
            scale: p.scale
          };
        })
    });
  });

  function clamp(value, min, max) { return Math.min(max, Math.max(min, value)); }

  renderTray();
  Object.keys(SLOTS).forEach(renderOptions);
})();

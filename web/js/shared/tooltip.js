export function createTooltipController() {
  let node = null;

  function ensure() {
    if (node && document.body.contains(node)) {
      return node;
    }
    const next = document.createElement("div");
    next.className = "cursor-tooltip";
    document.body.appendChild(next);
    node = next;
    return node;
  }

  function show(text, event) {
    const current = ensure();
    current.textContent = text;
    const offset = 14;
    const viewportWidth = window.innerWidth || document.documentElement.clientWidth || 1280;
    const viewportHeight = window.innerHeight || document.documentElement.clientHeight || 720;
    const rect = current.getBoundingClientRect();
    let x = event.clientX + offset;
    let y = event.clientY + offset;
    if (x + rect.width > viewportWidth - 8) {
      x = Math.max(8, event.clientX - rect.width - offset);
    }
    if (y + rect.height > viewportHeight - 8) {
      y = Math.max(8, event.clientY - rect.height - offset);
    }
    current.style.left = `${Math.round(x)}px`;
    current.style.top = `${Math.round(y)}px`;
    current.classList.add("visible");
  }

  function hide() {
    if (!node) {
      return;
    }
    node.classList.remove("visible");
  }

  return {
    ensure,
    show,
    hide,
  };
}

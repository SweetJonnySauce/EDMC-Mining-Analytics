export const DEFAULT_THEME_ID = "orange-dark";
export const THEME_OPTIONS = [
  { id: "blue-light", label: "Blue (light)", swatchBg: "#edf2f8", swatchAccent: "#3f87d4" },
  { id: "blue-dark", label: "Blue (dark)", swatchBg: "#0b1017", swatchAccent: "#3f87d4" },
  { id: "orange-dark", label: "Orange (dark)", swatchBg: "#130e09", swatchAccent: "#ff9f1a" },
  { id: "green-light", label: "Green (light)", swatchBg: "#f4f9f2", swatchAccent: "#3c8223" },
  { id: "green-dark", label: "Green (dark)", swatchBg: "#1a2a29", swatchAccent: "#86c948" },
];

export function createThemeController({
  rootElement,
  themeToggle,
  themeMenu,
  storageKey,
  defaultThemeId = DEFAULT_THEME_ID,
  themeOptions = THEME_OPTIONS,
  onThemeChange,
}) {
  const validThemes = new Set(themeOptions.map((option) => option.id));
  let activeThemeId = defaultThemeId;

  function getThemeOption(themeId) {
    return themeOptions.find((option) => option.id === themeId) || null;
  }

  function setThemeMenuOpen(open) {
    if (!themeToggle || !themeMenu) {
      return;
    }
    const isOpen = !!open;
    themeToggle.setAttribute("aria-expanded", isOpen ? "true" : "false");
    themeMenu.setAttribute("aria-hidden", isOpen ? "false" : "true");
    themeMenu.classList.toggle("theme-menu--open", isOpen);
  }

  function syncThemeControls() {
    if (!themeToggle || !themeMenu) {
      return;
    }
    const option = getThemeOption(activeThemeId) || getThemeOption(defaultThemeId);
    themeToggle.textContent = option ? `${option.label} ▾` : "Theme ▾";
    const buttons = themeMenu.querySelectorAll(".theme-option[data-theme-id]");
    buttons.forEach((button) => {
      const isActive = button.getAttribute("data-theme-id") === activeThemeId;
      button.classList.toggle("theme-option--active", isActive);
      button.setAttribute("aria-pressed", isActive ? "true" : "false");
    });
  }

  function applyTheme(themeId, persist) {
    const option = getThemeOption(themeId) || getThemeOption(defaultThemeId);
    if (!option) {
      return;
    }
    activeThemeId = option.id;
    if (rootElement) {
      rootElement.setAttribute("data-theme", option.id);
    }
    syncThemeControls();
    if (typeof onThemeChange === "function") {
      onThemeChange(option.id);
    }
    if (persist !== false) {
      try {
        window.localStorage.setItem(storageKey, option.id);
      } catch (_err) {
        // Ignore storage errors.
      }
    }
  }

  function renderThemeMenu() {
    if (!themeMenu) {
      return;
    }
    themeMenu.innerHTML = "";
    themeOptions.forEach((option) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "theme-option";
      button.setAttribute("data-theme-id", option.id);

      const swatch = document.createElement("span");
      swatch.className = "theme-swatch";
      swatch.style.setProperty("--swatch-bg", option.swatchBg);
      swatch.style.setProperty("--swatch-accent", option.swatchAccent);

      const label = document.createElement("span");
      label.textContent = option.label;

      button.appendChild(swatch);
      button.appendChild(label);
      button.addEventListener("click", () => {
        applyTheme(option.id);
        setThemeMenuOpen(false);
      });
      themeMenu.appendChild(button);
    });
  }

  function resolveThemeId() {
    try {
      const params = new URLSearchParams(window.location.search || "");
      const queryTheme = (params.get("theme") || "").trim();
      if (validThemes.has(queryTheme)) {
        return queryTheme;
      }
    } catch (_err) {
      // Ignore URL parsing issues.
    }
    try {
      const storedTheme = window.localStorage.getItem(storageKey) || "";
      if (validThemes.has(storedTheme)) {
        return storedTheme;
      }
    } catch (_err) {
      // Ignore storage issues.
    }
    return defaultThemeId;
  }

  function initialize() {
    if (!themeToggle || !themeMenu) {
      return;
    }
    renderThemeMenu();
    applyTheme(resolveThemeId(), false);

    themeToggle.addEventListener("click", (event) => {
      event.stopPropagation();
      const isOpen = themeMenu.classList.contains("theme-menu--open");
      setThemeMenuOpen(!isOpen);
    });
    themeMenu.addEventListener("click", (event) => {
      event.stopPropagation();
    });
    document.addEventListener("click", () => {
      setThemeMenuOpen(false);
    });
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        setThemeMenuOpen(false);
      }
    });
  }

  return {
    initialize,
    applyTheme,
    getActiveThemeId: () => activeThemeId,
  };
}

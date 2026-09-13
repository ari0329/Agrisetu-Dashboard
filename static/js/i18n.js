/* AgriSetu — Dashboard internationalization */

window.i18n = {
  lang: "en",
  strings: {},
  _enStrings: null,
  ready: null,

  async init(lang) {
    this.lang = lang || window.AGRISETU_LANG || "en";
    const res = await fetch(`/static/i18n/${encodeURIComponent(this.lang)}.json`);
    if (!res.ok) {
      const fallback = await fetch("/static/i18n/en.json");
      this.strings = await fallback.json();
    } else {
      this.strings = await res.json();
    }
    if (this.lang === "en") {
      this._enStrings = this.strings;
    } else {
      try {
        const enRes = await fetch("/static/i18n/en.json");
        this._enStrings = enRes.ok ? await enRes.json() : null;
      } catch {
        this._enStrings = null;
      }
    }
    document.documentElement.lang = this.lang;
    if (window.AGRISETU_LOGIN_PAGE && this.strings.login?.page_title) {
      document.title = this.strings.login.page_title;
    } else if (this.strings.meta?.title) {
      document.title = this.strings.meta.title;
    }
    this.applyDom();
    this.syncLanguageSelect();
    return this;
  },

  t(key, params = {}) {
    let text = this._lookup(key);
    if (text === key) {
      text = this._lookupEn(key) || key;
    }
    Object.entries(params).forEach(([name, value]) => {
      text = text.replace(new RegExp(`\\{${name}\\}`, "g"), String(value ?? ""));
    });
    return text;
  },

  _lookupEn(key) {
    if (!this._enStrings) return null;
    const parts = key.split(".");
    let node = this._enStrings;
    for (const part of parts) {
      if (!node || typeof node !== "object") return null;
      node = node[part];
    }
    return typeof node === "string" ? node : null;
  },

  _lookup(key) {
    const parts = key.split(".");
    let node = this.strings;
    for (const part of parts) {
      if (!node || typeof node !== "object") return key;
      node = node[part];
    }
    if (typeof node === "string") return node;
    return key;
  },

  applyDom() {
    document.querySelectorAll("[data-i18n]").forEach((el) => {
      el.textContent = this.t(el.dataset.i18n);
    });
    document.querySelectorAll("[data-i18n-placeholder]").forEach((el) => {
      el.placeholder = this.t(el.dataset.i18nPlaceholder);
    });
    document.querySelectorAll("[data-i18n-title]").forEach((el) => {
      el.title = this.t(el.dataset.i18nTitle);
    });
    document.querySelectorAll("[data-i18n-aria]").forEach((el) => {
      el.setAttribute("aria-label", this.t(el.dataset.i18nAria));
    });
    this.updateCropSelectOptions();
  },

  updateCropSelectOptions() {
    const select = document.getElementById("crop-select");
    if (!select) return;
    const value = select.value;
    const keys = [
      "", "wheat", "rice", "maize", "cotton", "soybean",
      "potato", "tomato", "sugarcane", "sunflower", "barley",
    ];
    const labels = [
      "ui.ai_decide",
      "ui.crop_wheat", "ui.crop_rice", "ui.crop_maize", "ui.crop_cotton",
      "ui.crop_soybean", "ui.crop_potato", "ui.crop_tomato", "ui.crop_sugarcane",
      "ui.crop_sunflower", "ui.crop_barley",
    ];
    select.innerHTML = keys.map((crop, idx) =>
      `<option value="${crop}">${this.t(labels[idx])}</option>`
    ).join("");
    select.value = value;
  },

  syncLanguageSelect() {
    const select = document.getElementById("lang-select")
      || document.getElementById("login-lang-select");
    if (select) select.value = this.lang;
  },

  getLocale() {
    const map = {
      en: "en-IN",
      hi: "hi-IN",
      bn: "bn-IN",
      ta: "ta-IN",
      mr: "mr-IN",
      te: "te-IN",
      kn: "kn-IN",
    };
    return map[this.lang] || "en-IN";
  },

  async setLanguage(lang) {
    if (!lang || lang === this.lang) return;
    const res = await fetch("/api/me/preferences", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ preferred_language: lang }),
    });
    const json = await res.json();
    if (!json.success) throw new Error(json.error || "Could not save language");
    window.AGRISETU_LANG = lang;
    await this.init(lang);
    if (typeof window.onLanguageChanged === "function") {
      window.onLanguageChanged();
    }
  },
};

window.t = (key, params) => window.i18n.t(key, params);

window.i18n.ready = (async () => {
  let initialLang = window.AGRISETU_LANG || "en";
  if (window.AGRISETU_LOGIN_PAGE) {
    try {
      const stored = localStorage.getItem("agrisetu_lang");
      if (stored) initialLang = stored;
    } catch {
      /* ignore */
    }
  }
  await window.i18n.init(initialLang);
  const langSelect = document.getElementById("lang-select")
    || document.getElementById("login-lang-select");
  if (langSelect) {
    langSelect.addEventListener("change", async (event) => {
      try {
        if (window.AGRISETU_LOGIN_PAGE) {
          window.AGRISETU_LANG = event.target.value;
          try {
            localStorage.setItem("agrisetu_lang", event.target.value);
          } catch {
            /* ignore */
          }
          await window.i18n.init(event.target.value);
          return;
        }
        await window.i18n.setLanguage(event.target.value);
      } catch (err) {
        if (typeof toast === "function") toast(err.message, "error");
        window.i18n.syncLanguageSelect();
      }
    });
  }
})();

document.addEventListener("DOMContentLoaded", () => {
  window.i18n.ready?.catch((err) => console.warn("i18n init failed:", err));
});

/**
 * Dark/light theme toggle for job-search-api local-ui.
 * Persists in localStorage; respects prefers-color-scheme if no saved theme.
 */
(function () {
    var STORAGE_KEY = "job_search_ui_theme";

    function getSavedTheme() {
        try {
            return localStorage.getItem(STORAGE_KEY);
        } catch (e) {
            return null;
        }
    }

    function setSavedTheme(theme) {
        try {
            if (theme) localStorage.setItem(STORAGE_KEY, theme);
            else localStorage.removeItem(STORAGE_KEY);
        } catch (e) {}
    }

    function getSystemTheme() {
        try {
            if (window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches) return "dark";
            if (window.matchMedia && window.matchMedia("(prefers-color-scheme: light)").matches) return "light";
        } catch (e) {}
        return "light";
    }

    function applyTheme(theme) {
        var doc = document.documentElement;
        if (theme === "dark") doc.setAttribute("data-theme", "dark");
        else doc.removeAttribute("data-theme");
    }

    function currentTheme() {
        return document.documentElement.getAttribute("data-theme") === "dark" ? "dark" : "light";
    }

    function updateToggleButton(btn) {
        if (!btn) return;
        var isDark = currentTheme() === "dark";
        btn.textContent = isDark ? "\u2600\uFE0F" : "\uD83C\uDF19";
        btn.setAttribute("aria-label", isDark ? "Switch to light mode" : "Switch to dark mode");
        btn.title = isDark ? "Light mode" : "Dark mode";
    }

    function updateAdminLinkEmoji(link) {
        if (!link) return;
        var isDark = currentTheme() === "dark";
        link.textContent = isDark ? "\u2699\uFE0F" : "\uD83D\uDD27";
    }

    function init() {
        var saved = getSavedTheme();
        var theme = saved === "dark" || saved === "light" ? saved : getSystemTheme();
        applyTheme(theme);

        var toggle = document.getElementById("theme-toggle");
        if (toggle) {
            updateToggleButton(toggle);
            toggle.addEventListener("click", function () {
                var next = currentTheme() === "dark" ? "light" : "dark";
                applyTheme(next);
                setSavedTheme(next);
                updateToggleButton(toggle);
                var adminLink = document.getElementById("admin-link");
                if (adminLink) updateAdminLinkEmoji(adminLink);
            });
        }

        var adminLink = document.getElementById("admin-link");
        if (adminLink) updateAdminLinkEmoji(adminLink);
    }

    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
    else init();
})();

// apps/creative_editor/static/creative_editor/admin/background_admin.js

(() => {
    "use strict";

    const byId = (id) => document.getElementById(id);

    const normalizeHex = (value) => {
        const cleaned = String(value || "")
            .trim()
            .replaceAll("#", "")
            .toUpperCase();

        if (/^[0-9A-F]{6}$/.test(cleaned)) {
            return `#${cleaned}`;
        }

        if (/^[0-9A-F]{8}$/.test(cleaned)) {
            /*
             CSS accepts #RRGGBBAA.
             */
            return `#${cleaned}`;
        }

        return null;
    };

    const parseGradientColors = (rawValue) => {
        try {
            const value = JSON.parse(rawValue || "[]");

            if (!Array.isArray(value)) {
                return [];
            }

            return value
                .map(normalizeHex)
                .filter(Boolean)
                .slice(0, 5);
        } catch {
            return [];
        }
    };

    const updatePreview = () => {
        const preview =
            byId("creative-background-live-preview");

        const values =
            byId("creative-background-preview-values");

        if (!preview) {
            return;
        }

        const typeInput =
            byId("id_background_type");

        const colorInput =
            byId("id_color");

        const colorsInput =
            byId("id_colors");

        const angleInput =
            byId("id_angle");

        const backgroundType =
            typeInput?.value || "color";

        if (backgroundType === "gradient") {
            const colors = parseGradientColors(
                colorsInput?.value
            );

            const safeColors =
                colors.length >= 2
                    ? colors
                    : ["#071A33", "#0F52BA"];

            const rawAngle = Number(
                angleInput?.value || 90
            );

            const angle = Number.isFinite(rawAngle)
                ? Math.max(-360, Math.min(360, rawAngle))
                : 90;

            preview.style.background =
                `linear-gradient(${angle}deg, ` +
                `${safeColors.join(", ")})`;

            if (values) {
                values.textContent =
                    `Gradient · ${angle}° · ` +
                    safeColors.join(" → ");
            }

            return;
        }

        const color =
            normalizeHex(colorInput?.value) ||
            "#0F52BA";

        preview.style.background = color;

        if (values) {
            values.textContent =
                `Solid · ${color}`;
        }
    };

    const attach = () => {
        [
            "id_background_type",
            "id_color",
            "id_colors",
            "id_angle",
        ].forEach((id) => {
            const element = byId(id);

            if (!element) {
                return;
            }

            element.addEventListener(
                "input",
                updatePreview
            );

            element.addEventListener(
                "change",
                updatePreview
            );
        });

        updatePreview();
    };

    if (document.readyState === "loading") {
        document.addEventListener(
            "DOMContentLoaded",
            attach
        );
    } else {
        attach();
    }
})();